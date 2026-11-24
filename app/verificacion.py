"""Detección de cifras inventadas (P2): toda cifra de una respuesta debe venir de los hechos
calculados o del mensaje del usuario. Se usa en la redacción con LLM y en la evaluación (RF-28)."""
from __future__ import annotations

import re

RE_NUMERO = re.compile(r"\d[\d.,]*\d|\d")


def _valor(token: str) -> float | None:
    t = token.strip(".,")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", t):  # 1.234.567 o 1.234,5 (formato chileno)
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d+,\d+", t):
        return float(t.replace(",", "."))
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)
    try:
        return float(t.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _claves(v: float) -> set[str]:
    v = abs(v)
    return {f"{v:.2f}", f"{round(v):.2f}", f"{round(v, 1):.2f}"}


def numeros(texto: str) -> set[str]:
    salida: set[str] = set()
    for token in RE_NUMERO.findall(texto or ""):
        v = _valor(token)
        if v is not None:
            salida.add(f"{abs(v):.2f}")
    return salida


def permitidos(hechos, *textos: str) -> set[str]:
    salida: set[str] = set()

    def recorrer(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            salida.update(_claves(float(x)))
        elif isinstance(x, str):
            for token in RE_NUMERO.findall(x):
                v = _valor(token)
                if v is not None:
                    salida.update(_claves(v))
            for parte in re.findall(r"\d+", x):  # componentes de fechas ISO
                salida.update(_claves(float(parte)))
        elif isinstance(x, dict):
            for k, v in x.items():
                recorrer(k)
                recorrer(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                recorrer(v)

    recorrer(hechos)
    for t in textos:
        recorrer(t)
    return salida


def cifras_no_fundamentadas(respuesta: str, hechos, *textos: str) -> list[str]:
    ok = permitidos(hechos, *textos)
    return sorted(n for n in numeros(respuesta) if n not in ok)
