"""RF-01, RF-02, RF-14 (NLU por reglas)."""
from datetime import date

import pytest

from app import reglas

HOY = date(2026, 11, 24)


@pytest.mark.parametrize("texto,esperado", [
    ("gasté 25 lucas", 25000),
    ("$45.990 de luz", 45990),
    ("1,5 millones", 1500000),
    ("2 palos", 2000000),
    ("12 mil en uber", 12000),
    ("me pagaron 1.850.000", 1850000),
    ("quince lucas", 15000),
    ("el 3 de marzo gasté 20.000", 20000),
    ("10 acciones a $41.000", 41000),
])
def test_montos(texto, esperado):
    assert reglas.parse_monto(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("ayer", "2026-11-23"),
    ("hoy", "2026-11-24"),
    ("anteayer", "2026-11-22"),
    ("el 20 de noviembre", "2026-11-20"),
    ("el 3 de diciembre", "2025-12-03"),
    ("el viernes", "2026-11-20"),
    ("el 03/11/2026", "2026-11-03"),
])
def test_fechas(texto, esperado):
    assert reglas.parse_fecha(texto, HOY) == esperado


@pytest.mark.parametrize("texto,desde,hasta", [
    ("este mes", "2026-11-01", "2026-11-24"),
    ("el mes pasado", "2026-10-01", "2026-10-31"),
    ("los últimos 6 meses", "2026-06-01", "2026-11-24"),
    ("este año", "2026-01-01", "2026-11-24"),
    ("en octubre", "2026-10-01", "2026-10-31"),
    ("entre marzo y junio", "2026-03-01", "2026-06-30"),
    ("desde junio", "2026-06-01", "2026-11-24"),
    ("la semana pasada", "2026-11-16", "2026-11-22"),
])
def test_periodos(texto, desde, hasta):
    assert reglas.parse_periodo(texto, HOY) == {"desde": desde, "hasta": hasta}


def test_tickers():
    assert reglas.detectar_tickers("compara sqm con falabella") == ["SQM-B", "FALABELLA"]
    assert reglas.detectar_tickers("Santander vs Banco de Chile") == ["BSANTANDER", "CHILE"]
    assert reglas.detectar_tickers("vendí AAPL") == ["AAPL"]


@pytest.mark.parametrize("texto,intencion", [
    ("gasté 25 lucas en el súper ayer", "registrar_gasto"),
    ("me pagaron el sueldo", "registrar_ingreso"),
    ("compré 10 acciones de SQM-B a 41.000", "registrar_compra"),
    ("vendí 5 acciones de Copec", "registrar_venta"),
    ("¿cuánta plata tengo?", "consultar_saldo"),
    ("muéstrame mi portafolio", "consultar_portafolio"),
    ("¿cuánto gasté en transporte el mes pasado?", "consultar_movimientos"),
    ("gráfico de ingresos vs gastos", "grafico_ingresos_egresos"),
    ("compara SQM-B y Falabella este año", "grafico_comparar_acciones"),
    ("¿cómo ha evolucionado mi patrimonio?", "grafico_linea_tiempo"),
    ("¿en qué se me va la plata?", "grafico_gastos_categoria"),
    ("¿me conviene invertir en fondos mutuos?", "consejo_inversion"),
    ("hola", "saludo"),
    ("¿qué puedes hacer?", "ayuda"),
    ("chao", "despedida"),
    ("¿quién ganó el partido?", "fuera_de_dominio"),
])
def test_intenciones(texto, intencion):
    assert reglas.detectar_intencion(texto) == intencion


def test_serie_en_linea():
    r = reglas.interpretar("grafica mis ingresos: enero 1.200.000, febrero 980.000, marzo 1.050.000", HOY)
    assert r["intencion"] == "grafico_linea_tiempo"
    assert r["entidades"]["serie"] == [["Enero", 1200000], ["Febrero", 980000], ["Marzo", 1050000]]
    assert "periodo" not in r["entidades"]


def test_compra_con_total():
    e = reglas.interpretar("compré 100 acciones de copec por 650 mil en total", HOY)["entidades"]
    assert e == {"ticker": "COPEC", "cantidad": 100.0, "precio": 6500.0}
