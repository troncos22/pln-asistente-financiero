"""API REST y servidor de la interfaz web (RF-24). Ejecutar con:  python -m app"""
from __future__ import annotations

import csv
import io
import re
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auditoria, db, guard, masking, seed
from .asistente import Asistente
from .config import CONFIG
from .reglas import CATEGORIAS_GASTO, CATEGORIAS_INGRESO

ESTATICOS = Path(__file__).parent / "static"

con = db.conectar(CONFIG.db_path)
if con.execute("SELECT COUNT(*) FROM movimientos").fetchone()[0] == 0 and \
        con.execute("SELECT COUNT(*) FROM precios").fetchone()[0] == 0:
    seed.sembrar(con)
asistente = Asistente(con)

app = FastAPI(title="Asistente financiero personal — Lang-Chi", version="0.1.0")
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")


class MensajeChat(BaseModel):
    sesion_id: str = Field(default="web", max_length=64)
    mensaje: str = Field(min_length=1, max_length=4000)


@app.get("/")
def inicio():
    return FileResponse(ESTATICOS / "index.html")


@app.get("/api/estado")
def estado():
    return {"modelo": CONFIG.modelo, "llm_disponible": asistente.llm.disponible(), "nlu_modo": CONFIG.nlu_modo,
            "respuesta_modo": CONFIG.respuesta_modo, "hoy": CONFIG.hoy.isoformat(),
            "umbral_inyeccion": CONFIG.umbral_inyeccion}


@app.post("/api/chat")
def chat(m: MensajeChat):
    return asistente.procesar(m.sesion_id, m.mensaje)


@app.get("/api/resumen")
def resumen():
    hoy = CONFIG.hoy
    caja = db.caja(con, hoy)
    acciones = db.valor_portafolio(con, hoy)
    mes = db.totales_periodo(con, date(hoy.year, hoy.month, 1), hoy)
    return {"caja": caja, "acciones": round(acciones), "patrimonio": round(caja + acciones),
            "ingresos_mes": mes["ingresos"], "gastos_mes": mes["gastos"], "hoy": hoy.isoformat()}


@app.get("/api/movimientos")
def movimientos(limite: int = 30):
    return db.ultimos_movimientos(con, min(max(limite, 1), 500))


@app.get("/api/portafolio")
def portafolio():
    hoy = CONFIG.hoy
    salida = []
    for ticker, p in sorted(db.posiciones(con, hoy).items()):
        up = db.ultimo_precio(con, ticker, hoy)
        precio = up[1] if up else p["costo_promedio"]
        valor = p["cantidad"] * precio
        costo = p["cantidad"] * p["costo_promedio"]
        salida.append({"ticker": ticker, "cantidad": p["cantidad"], "costo_promedio": round(p["costo_promedio"], 2),
                       "precio": precio, "fecha_precio": up[0] if up else None, "valor": round(valor),
                       "ganancia": round(valor - costo), "pct": round((valor / costo - 1) * 100, 2) if costo else 0})
    return salida


@app.get("/api/auditoria")
def ver_auditoria(limite: int = 50):
    return auditoria.ultimos(con, min(max(limite, 1), 500))


def _leer_csv(archivo: UploadFile) -> list[dict]:
    contenido = archivo.file.read(2_000_000).decode("utf-8-sig", errors="replace")
    muestra = contenido[:2000]
    delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
    return list(csv.DictReader(io.StringIO(contenido), delimiter=delimitador))


def _monto(texto: str) -> float:
    t = re.sub(r"[^\d,.-]", "", texto or "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    return float(t.replace(",", "."))


@app.post("/api/importar/movimientos")
def importar_movimientos(archivo: UploadFile = File(...)):
    """CSV con columnas fecha,tipo,monto,categoria,descripcion (RF-22)."""
    filas = _leer_csv(archivo)
    importadas, rechazadas, tipos_enmascarados, bloqueadas = 0, [], [], 0
    for i, f in enumerate(filas, start=2):
        try:
            fecha = date.fromisoformat((f.get("fecha") or "").strip()).isoformat()
            tipo = (f.get("tipo") or "").strip().lower()
            monto = abs(_monto(f.get("monto", "")))
            if tipo not in ("ingreso", "gasto") or monto <= 0:
                raise ValueError("tipo o monto inválido")
            categoria = (f.get("categoria") or "otros").strip().lower()
            validas = CATEGORIAS_GASTO if tipo == "gasto" else CATEGORIAS_INGRESO
            categoria = categoria if categoria in validas else "otros"
            m = masking.enmascarar((f.get("descripcion") or "")[:200])
            tipos_enmascarados += m.tipos
            descripcion = m.texto
            if guard.puntuar(descripcion, CONFIG.umbral_inyeccion).bloqueado:
                descripcion, bloqueadas = "[DESCRIPCION BLOQUEADA]", bloqueadas + 1
            db.insertar_movimiento(con, fecha, tipo, int(round(monto)), categoria, descripcion, "csv")
            importadas += 1
        except (ValueError, TypeError) as error:
            rechazadas.append({"fila": i, "motivo": str(error)[:120]})
    resultado = {"importadas": importadas, "rechazadas": rechazadas[:50], "enmascarados": tipos_enmascarados,
                 "descripciones_bloqueadas": bloqueadas}
    auditoria.registrar(con, "web", "importar_movimientos", resultado, CONFIG.auditoria_jsonl)
    return resultado


@app.post("/api/importar/precios")
def importar_precios(archivo: UploadFile = File(...)):
    """CSV con columnas fecha,ticker,precio."""
    filas = _leer_csv(archivo)
    importadas, rechazadas = 0, []
    for i, f in enumerate(filas, start=2):
        try:
            fecha = date.fromisoformat((f.get("fecha") or "").strip()).isoformat()
            ticker = (f.get("ticker") or "").strip().upper()
            if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
                raise ValueError("ticker inválido")
            precio = _monto(f.get("precio", ""))
            if precio <= 0:
                raise ValueError("precio inválido")
            db.guardar_precio(con, fecha, ticker, precio, "csv")
            importadas += 1
        except (ValueError, TypeError) as error:
            rechazadas.append({"fila": i, "motivo": str(error)[:120]})
    con.commit()
    resultado = {"importadas": importadas, "rechazadas": rechazadas[:50]}
    auditoria.registrar(con, "web", "importar_precios", resultado, CONFIG.auditoria_jsonl)
    return resultado


@app.exception_handler(ValueError)
def error_valor(_, error: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(error)[:200]})
