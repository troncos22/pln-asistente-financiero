"""Base de datos SQLite: esquema, inserciones y consultas agregadas (RF-05 … RF-13).

Todas las cifras que ve el usuario salen de estas funciones (principio P2).
"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
    monto INTEGER NOT NULL CHECK (monto > 0),
    categoria TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL DEFAULT 'chat'
);
CREATE TABLE IF NOT EXISTS operaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('compra', 'venta')),
    ticker TEXT NOT NULL,
    cantidad REAL NOT NULL CHECK (cantidad > 0),
    precio REAL NOT NULL CHECK (precio > 0),
    origen TEXT NOT NULL DEFAULT 'chat'
);
CREATE TABLE IF NOT EXISTS precios (
    fecha TEXT NOT NULL,
    ticker TEXT NOT NULL,
    precio REAL NOT NULL,
    origen TEXT NOT NULL DEFAULT 'demo',
    PRIMARY KEY (fecha, ticker)
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    sesion TEXT NOT NULL,
    evento TEXT NOT NULL,
    detalle TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mov_fecha ON movimientos (fecha);
CREATE INDEX IF NOT EXISTS idx_op_ticker ON operaciones (ticker, fecha);
CREATE INDEX IF NOT EXISTS idx_precio_ticker ON precios (ticker, fecha);
"""


def conectar(ruta: Path | str) -> sqlite3.Connection:
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(ruta), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


# ---------------------------------------------------------------- utilidades de fechas

def fin_de_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def meses_entre(desde: date, hasta: date) -> list[str]:
    """Lista de meses 'AAAA-MM' entre dos fechas, ambos incluidos."""
    meses, a, m = [], desde.year, desde.month
    while (a, m) <= (hasta.year, hasta.month):
        meses.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return meses


# ---------------------------------------------------------------- escritura

def insertar_movimiento(con, fecha: str, tipo: str, monto: int, categoria: str,
                        descripcion: str = "", origen: str = "chat") -> int:
    cur = con.execute(
        "INSERT INTO movimientos (fecha, tipo, monto, categoria, descripcion, origen) VALUES (?,?,?,?,?,?)",
        (fecha, tipo, int(monto), categoria, descripcion, origen),
    )
    con.commit()
    return cur.lastrowid


def insertar_operacion(con, fecha: str, tipo: str, ticker: str, cantidad: float, precio: float,
                       origen: str = "chat") -> int:
    cur = con.execute(
        "INSERT INTO operaciones (fecha, tipo, ticker, cantidad, precio, origen) VALUES (?,?,?,?,?,?)",
        (fecha, tipo, ticker, float(cantidad), float(precio), origen),
    )
    con.commit()
    return cur.lastrowid


def guardar_precio(con, fecha: str, ticker: str, precio: float, origen: str = "demo") -> None:
    con.execute(
        "INSERT OR REPLACE INTO precios (fecha, ticker, precio, origen) VALUES (?,?,?,?)",
        (fecha, ticker, float(precio), origen),
    )


# ---------------------------------------------------------------- consultas

def caja(con, hasta: date | None = None) -> int:
    """Caja = ingresos − gastos − compras + ventas (RF-07)."""
    h = (hasta or date.max).isoformat()
    mov = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE -monto END),0) FROM movimientos WHERE fecha<=?",
        (h,),
    ).fetchone()[0]
    ops = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN tipo='venta' THEN cantidad*precio ELSE -cantidad*precio END),0) "
        "FROM operaciones WHERE fecha<=?",
        (h,),
    ).fetchone()[0]
    return int(round(mov + ops))


def posiciones(con, hasta: date | None = None) -> dict[str, dict]:
    """Cantidad y costo promedio ponderado por ticker (RF-08)."""
    h = (hasta or date.max).isoformat()
    pos: dict[str, dict] = {}
    for r in con.execute(
        "SELECT ticker, tipo, cantidad, precio FROM operaciones WHERE fecha<=? ORDER BY fecha, id", (h,)
    ):
        p = pos.setdefault(r["ticker"], {"cantidad": 0.0, "costo_promedio": 0.0})
        if r["tipo"] == "compra":
            total = p["cantidad"] * p["costo_promedio"] + r["cantidad"] * r["precio"]
            p["cantidad"] += r["cantidad"]
            p["costo_promedio"] = total / p["cantidad"]
        else:
            p["cantidad"] -= r["cantidad"]
    return {t: p for t, p in pos.items() if p["cantidad"] > 1e-9}


def ultimo_precio(con, ticker: str, hasta: date | None = None) -> tuple[str, float] | None:
    h = (hasta or date.max).isoformat()
    r = con.execute(
        "SELECT fecha, precio FROM precios WHERE ticker=? AND fecha<=? ORDER BY fecha DESC LIMIT 1", (ticker, h)
    ).fetchone()
    return (r["fecha"], r["precio"]) if r else None


def tickers_disponibles(con) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT ticker FROM precios ORDER BY ticker")]


def valor_portafolio(con, hasta: date | None = None) -> float:
    total = 0.0
    for ticker, p in posiciones(con, hasta).items():
        up = ultimo_precio(con, ticker, hasta)
        total += p["cantidad"] * (up[1] if up else p["costo_promedio"])
    return total


def totales_periodo(con, desde: date, hasta: date, tipo: str | None = None,
                    categoria: str | None = None) -> dict:
    filtros, args = ["fecha BETWEEN ? AND ?"], [desde.isoformat(), hasta.isoformat()]
    if tipo:
        filtros.append("tipo=?")
        args.append(tipo)
    if categoria:
        filtros.append("categoria=?")
        args.append(categoria)
    where = " AND ".join(filtros)
    filas = con.execute(
        f"SELECT tipo, categoria, SUM(monto) total, COUNT(*) n FROM movimientos WHERE {where} GROUP BY tipo, categoria",
        args,
    ).fetchall()
    res = {"ingresos": 0, "gastos": 0, "n": 0, "por_categoria": {}}
    for f in filas:
        res["ingresos" if f["tipo"] == "ingreso" else "gastos"] += f["total"]
        res["n"] += f["n"]
        res["por_categoria"][f"{f['tipo']}:{f['categoria']}"] = f["total"]
    res["mayores"] = [
        dict(r) for r in con.execute(
            f"SELECT fecha, tipo, monto, categoria, descripcion FROM movimientos WHERE {where} "
            "ORDER BY monto DESC LIMIT 3",
            args,
        )
    ]
    return res


def mensual(con, desde: date, hasta: date) -> list[dict]:
    """Ingresos y gastos por mes, incluyendo meses sin movimientos."""
    filas = {
        r["mes"]: r for r in con.execute(
            "SELECT substr(fecha,1,7) mes, "
            "SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END) ingresos, "
            "SUM(CASE WHEN tipo='gasto' THEN monto ELSE 0 END) gastos "
            "FROM movimientos WHERE fecha BETWEEN ? AND ? GROUP BY mes",
            (desde.isoformat(), hasta.isoformat()),
        )
    }
    return [
        {"mes": m, "ingresos": filas[m]["ingresos"] if m in filas else 0,
         "gastos": filas[m]["gastos"] if m in filas else 0}
        for m in meses_entre(desde, hasta)
    ]


def _cierre(mes: str, hasta: date) -> date:
    a, m = int(mes[:4]), int(mes[5:])
    return min(fin_de_mes(a, m), hasta)


def serie_caja(con, desde: date, hasta: date) -> list[tuple[str, int]]:
    return [(m, caja(con, _cierre(m, hasta))) for m in meses_entre(desde, hasta)]


def serie_patrimonio(con, desde: date, hasta: date) -> list[tuple[str, int]]:
    return [
        (m, int(round(caja(con, _cierre(m, hasta)) + valor_portafolio(con, _cierre(m, hasta)))))
        for m in meses_entre(desde, hasta)
    ]


def serie_precios(con, ticker: str, desde: date, hasta: date) -> list[tuple[str, float]]:
    return [
        (r["fecha"], r["precio"]) for r in con.execute(
            "SELECT fecha, precio FROM precios WHERE ticker=? AND fecha BETWEEN ? AND ? ORDER BY fecha",
            (ticker, desde.isoformat(), hasta.isoformat()),
        )
    ]


def gastos_por_categoria(con, desde: date, hasta: date) -> list[tuple[str, int]]:
    return [
        (r["categoria"], r["total"]) for r in con.execute(
            "SELECT categoria, SUM(monto) total FROM movimientos WHERE tipo='gasto' AND fecha BETWEEN ? AND ? "
            "GROUP BY categoria ORDER BY total DESC",
            (desde.isoformat(), hasta.isoformat()),
        )
    ]


def ultimos_movimientos(con, limite: int = 20) -> list[dict]:
    return [
        dict(r) for r in con.execute(
            "SELECT id, fecha, tipo, monto, categoria, descripcion, origen FROM movimientos "
            "ORDER BY fecha DESC, id DESC LIMIT ?",
            (limite,),
        )
    ]
