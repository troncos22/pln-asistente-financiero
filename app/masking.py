"""Detección y enmascarado de datos sensibles (RF-16, RF-17, RF-18).

El enmascarado es irreversible: el valor original no se guarda en ninguna parte. Los montos
de dinero NO se enmascaran porque son necesarios para la función del asistente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Enmascarado:
    texto: str
    tipos: list[str] = field(default_factory=list)  # tipos encontrados, sin valores


def rut_valido(cuerpo: str, dv: str) -> bool:
    """Dígito verificador del RUT chileno (módulo 11)."""
    digitos = re.sub(r"\D", "", cuerpo)
    if not digitos:
        return False
    suma, factor = 0, 2
    for d in reversed(digitos):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    return esperado == dv.upper()


def luhn_valido(numero: str) -> bool:
    digitos = [int(c) for c in numero if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _ultimos4(valor: str) -> str:
    return re.sub(r"\D", "", valor)[-4:]


RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_CLAVE = re.compile(
    r"\b(clave|contrase[ñn]a|password|pass|pin|cvv|cvc|c[oó]digo de (?:seguridad|verificaci[oó]n))"
    r"((?:\s+(?:secreta|din[aá]mica|de internet|del? \w+|de la \w+))?(?:\s*(?:es|era|:|=)\s*|\s+))([^\s,;]+)",
    re.IGNORECASE,
)
RE_TARJETA = re.compile(r"(?<![\d.,$])(?:\d[ -]?){12,18}\d(?![\d])")
RE_CUENTA = re.compile(
    r"\b(cuenta|cta\.?)(\s+(?:corriente|vista|rut|de ahorros?|bancaria))?"
    r"(\s*(?:n[°ºo]\.?|nro\.?|n[uú]mero|#))?\s*:?\s*(\d[\d-]{5,19}\d)\b",
    re.IGNORECASE,
)
RE_RUT = re.compile(r"(?<![\d.])(\d{1,2}\.?\d{3}\.?\d{3})-([\dkK])\b")
RE_RUT_SIN_GUION = re.compile(r"\b(rut|run)(\s*(?:es|:)?\s*)(\d{7,8})([\dkK])\b", re.IGNORECASE)
RE_TELEFONO = re.compile(r"(?<![\d$])(?:\+?56[\s-]?)?(?:9|2)[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


def enmascarar(texto: str) -> Enmascarado:
    tipos: list[str] = []
    actual = [texto]  # texto vigente antes de cada sustitución, para mirar el contexto

    def correo(m):
        tipos.append("correo")
        return "[CORREO]"

    def clave(m):
        if m.group(3).startswith("["):  # ya enmascarado
            return m.group(0)
        tipos.append("clave")
        return f"{m.group(1)}{m.group(2)}[CLAVE]"

    def tarjeta(m):
        valor = m.group(0)
        digitos = re.sub(r"\D", "", valor)
        contexto = actual[0][max(0, m.start() - 30):m.start()].lower()
        if 13 <= len(digitos) <= 19 and (luhn_valido(digitos) or "tarjeta" in contexto):
            tipos.append("tarjeta")
            return f"[TARJETA ****{digitos[-4:]}]"
        return valor

    def cuenta(m):
        numero = m.group(4)
        calificada = bool(m.group(2) or m.group(3))
        if calificada or len(re.sub(r"\D", "", numero)) >= 8:
            tipos.append("cuenta")
            return m.group(0)[: m.start(4) - m.start(0)] + f"[CUENTA ****{_ultimos4(numero)}]"
        return m.group(0)

    def rut(m):
        contexto = actual[0][max(0, m.start() - 12):m.start()].lower()
        if rut_valido(m.group(1), m.group(2)) or "rut" in contexto or "run" in contexto:
            tipos.append("rut")
            return "[RUT]"
        return m.group(0)

    def rut_sin_guion(m):
        tipos.append("rut")
        return f"{m.group(1)}{m.group(2)}[RUT]"

    def telefono(m):
        tipos.append("telefono")
        return "[TELEFONO]"

    for patron, funcion in (
        (RE_CORREO, correo), (RE_CLAVE, clave), (RE_TARJETA, tarjeta), (RE_CUENTA, cuenta),
        (RE_RUT, rut), (RE_RUT_SIN_GUION, rut_sin_guion), (RE_TELEFONO, telefono),
    ):
        actual[0] = patron.sub(funcion, actual[0])
    return Enmascarado(actual[0], tipos)


def enmascarar_texto(texto: str) -> str:
    return enmascarar(texto).texto
