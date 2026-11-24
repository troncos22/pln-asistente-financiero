"""Datos de ejemplo SINTÉTICOS y reproducibles (RF-27).

Los precios de acciones son simulados (paseo aleatorio geométrico con semilla fija); no son
cotizaciones reales. Uso:  python -m app.seed --reset
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import date, timedelta

from . import db
from .config import CONFIG

# nemotécnico: (precio inicial simulado, deriva anual, volatilidad anual)
ACCIONES = {
    "SQM-B": (42000, 0.05, 0.40),
    "FALABELLA": (3800, 0.10, 0.30),
    "COPEC": (6500, 0.04, 0.22),
    "BSANTANDER": (55, 0.08, 0.18),
    "CHILE": (118, 0.09, 0.17),
    "CENCOSUD": (1900, 0.02, 0.28),
    "ENELCHILE": (60, 0.03, 0.20),
    "LTM": (16, 0.20, 0.35),
}


def _restar_meses(d: date, n: int) -> date:
    a, m = d.year, d.month - n
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


def _precios(con, rng: random.Random, desde: date, hasta: date) -> None:
    for ticker, (p0, mu, sigma) in ACCIONES.items():
        precio, d, dt = float(p0), desde, 1 / 252
        while d <= hasta:
            if d.weekday() < 5:
                precio *= math.exp((mu - sigma**2 / 2) * dt + sigma * math.sqrt(dt) * rng.gauss(0, 1))
                decimales = 2 if precio < 1000 else 0
                db.guardar_precio(con, d.isoformat(), ticker, round(precio, decimales), "demo")
            d += timedelta(days=1)
    con.commit()


def _dia(anio: int, mes: int, dia: int, hoy: date) -> date | None:
    d = date(anio, mes, min(dia, db.fin_de_mes(anio, mes).day))
    return d if d <= hoy else None


def sembrar(con, hoy: date | None = None, semilla: int = 42) -> None:
    hoy = hoy or CONFIG.hoy
    rng = random.Random(semilla)
    inicio = _restar_meses(hoy, 11)
    _precios(con, rng, _restar_meses(hoy, 12), hoy)

    def mov(d, tipo, monto, cat, desc):
        if d:
            db.insertar_movimiento(con, d.isoformat(), tipo, int(monto), cat, desc, "demo")

    mov(inicio, "ingreso", 2_000_000, "otros", "Saldo inicial cuenta")
    for i, mes in enumerate(db.meses_entre(inicio, hoy)):
        a, m = int(mes[:4]), int(mes[5:])
        mov(_dia(a, m, 30, hoy), "ingreso", 1_850_000, "sueldo", "Sueldo")
        if i % 3 == 1:
            mov(_dia(a, m, 15, hoy), "ingreso", rng.randrange(300, 520) * 1000, "honorarios", "Boleta de honorarios")
        mov(_dia(a, m, 5, hoy), "gasto", 450_000, "vivienda", "Arriendo departamento")
        mov(_dia(a, m, 10, hoy), "gasto", rng.randrange(32, 58) * 1000, "servicios", "Cuenta de la luz")
        mov(_dia(a, m, 11, hoy), "gasto", rng.randrange(14, 26) * 1000, "servicios", "Cuenta del agua")
        mov(_dia(a, m, 12, hoy), "gasto", 25_990, "servicios", "Internet hogar")
        for semana in range(4):
            mov(_dia(a, m, 3 + semana * 7, hoy), "gasto", rng.randrange(38, 95) * 1000, "alimentacion", "Supermercado")
        for _ in range(rng.randrange(5, 9)):
            mov(_dia(a, m, rng.randrange(1, 29), hoy), "gasto", rng.randrange(2, 15) * 1000, "transporte",
                rng.choice(["Uber", "Carga tarjeta bip", "Bencina"]))
        for _ in range(rng.randrange(1, 4)):
            mov(_dia(a, m, rng.randrange(1, 29), hoy), "gasto", rng.randrange(8, 42) * 1000, "entretencion",
                rng.choice(["Cine", "Salida a comer", "Streaming", "Concierto"]))
        if rng.random() < 0.7:
            mov(_dia(a, m, rng.randrange(1, 29), hoy), "gasto", rng.randrange(6, 35) * 1000, "salud", "Farmacia")
        if rng.random() < 0.3:
            mov(_dia(a, m, rng.randrange(1, 29), hoy), "gasto", rng.randrange(20, 90) * 1000, "ropa", "Ropa")

    compras = [(1, "SQM-B", 20), (2, "FALABELLA", 300), (4, "COPEC", 100), (6, "CHILE", 5000)]
    for desplazamiento, ticker, cantidad in compras:
        d = _restar_meses(hoy, 11 - desplazamiento) + timedelta(days=16)
        _, precio = db.ultimo_precio(con, ticker, d)
        db.insertar_operacion(con, d.isoformat(), "compra", ticker, cantidad, precio, "demo")
    d = _restar_meses(hoy, 2) + timedelta(days=8)
    _, precio = db.ultimo_precio(con, "SQM-B", d)
    db.insertar_operacion(con, d.isoformat(), "venta", "SQM-B", 5, precio, "demo")
    con.commit()


def reiniciar(con) -> None:
    for tabla in ("movimientos", "operaciones", "precios"):
        con.execute(f"DELETE FROM {tabla}")
    con.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Carga datos de ejemplo sintéticos")
    ap.add_argument("--reset", action="store_true", help="borra movimientos, operaciones y precios antes de sembrar")
    args = ap.parse_args()
    conexion = db.conectar(CONFIG.db_path)
    if args.reset:
        reiniciar(conexion)
    sembrar(conexion)
    print(f"Datos de ejemplo cargados en {CONFIG.db_path} (hoy={CONFIG.hoy})")
