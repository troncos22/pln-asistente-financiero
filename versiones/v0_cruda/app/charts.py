"""Especificaciones de gráficos (RF-10 … RF-15). Solo datos JSON; el frontend los dibuja con Chart.js."""
from __future__ import annotations

from datetime import date

from . import db

TITULOS_METRICA = {"saldo": "Saldo disponible (caja)", "patrimonio": "Patrimonio (caja + acciones)",
                   "ingresos": "Ingresos mensuales", "gastos": "Gastos mensuales"}


def _spec(tipo: str, titulo: str, etiquetas: list, series: list[dict], unidad: str = "CLP", nota: str = "") -> dict:
    return {"tipo": tipo, "titulo": titulo, "etiquetas": etiquetas, "series": series, "unidad": unidad, "nota": nota}


def linea_tiempo(con, metrica: str, desde: date, hasta: date) -> dict:
    if metrica == "patrimonio":
        puntos = db.serie_patrimonio(con, desde, hasta)
    elif metrica in ("ingresos", "gastos"):
        puntos = [(f["mes"], f[metrica]) for f in db.mensual(con, desde, hasta)]
    else:
        metrica, puntos = "saldo", db.serie_caja(con, desde, hasta)
    return _spec("line", f"{TITULOS_METRICA[metrica]} {desde:%m/%Y}–{hasta:%m/%Y}", [p[0] for p in puntos],
                 [{"nombre": metrica.capitalize(), "datos": [p[1] for p in puntos]}])


def ingresos_egresos(con, desde: date, hasta: date) -> dict:
    filas = db.mensual(con, desde, hasta)
    return _spec(
        "bar", f"Ingresos vs egresos {desde:%m/%Y}–{hasta:%m/%Y}", [f["mes"] for f in filas],
        [
            {"nombre": "Ingresos", "datos": [f["ingresos"] for f in filas]},
            {"nombre": "Egresos", "datos": [f["gastos"] for f in filas]},
            {"nombre": "Neto", "datos": [f["ingresos"] - f["gastos"] for f in filas], "tipo": "line"},
        ],
    )


def comparar_acciones(con, tickers: list[str], desde: date, hasta: date) -> dict:
    series_crudas = {t: db.serie_precios(con, t, desde, hasta) for t in tickers}
    fechas = sorted({f for s in series_crudas.values() for f, _ in s})
    if (hasta - desde).days > 92:  # semanal: un punto por semana (último día hábil disponible)
        por_semana: dict[str, str] = {}
        for f in fechas:
            por_semana[date.fromisoformat(f).strftime("%G-%V")] = f
        fechas = sorted(por_semana.values())
    normalizar = len(tickers) > 1
    series = []
    for t, puntos in series_crudas.items():
        mapa = dict(puntos)
        datos, base = [], None
        for f in fechas:
            v = mapa.get(f)
            if v is not None and base is None:
                base = v
            datos.append(round(v / base * 100, 2) if (v is not None and normalizar) else v)
        series.append({"nombre": t, "datos": datos})
    return _spec(
        "line", ("Comparación de acciones (base 100)" if normalizar else f"Precio de {tickers[0]}")
        + f" {desde:%m/%Y}–{hasta:%m/%Y}",
        fechas, series, "base 100" if normalizar else "CLP",
        "Precios simulados (datos de ejemplo)" if any(_es_demo(con, t) for t in tickers) else "",
    )


def _es_demo(con, ticker: str) -> bool:
    r = con.execute("SELECT 1 FROM precios WHERE ticker=? AND origen='demo' LIMIT 1", (ticker,)).fetchone()
    return r is not None


def gastos_categoria(con, desde: date, hasta: date) -> dict:
    filas = db.gastos_por_categoria(con, desde, hasta)
    return _spec("doughnut", f"Gastos por categoría {desde:%d/%m/%Y}–{hasta:%d/%m/%Y}",
                 [f[0] for f in filas], [{"nombre": "Gastos", "datos": [f[1] for f in filas]}])


def desde_serie(serie: list[list], titulo: str, nombre: str) -> dict:
    """Gráfico con datos entregados por el usuario en el mensaje (RF-14)."""
    return _spec("line" if len(serie) > 2 else "bar", titulo, [s[0] for s in serie],
                 [{"nombre": nombre, "datos": [s[1] for s in serie]}], nota="Datos ingresados en el mensaje")
