"""Defensa contra prompt injection (RF-19, RF-21, RF-22, RF-23).

Capa 1 del plan (§6): detector de patrones con normalización. Las demás capas (delimitación,
salida estructurada con lista blanca, canario y verificación de salida) están en nlu.py, llm.py
y asistente.py.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Si esta cadena aparece en una salida del LLM, el modelo filtró su prompt de sistema.
CANARIO = "LANGCHI-CANARIO-7F3A9C"

RESPUESTA_BLOQUEO = (
    "No puedo procesar ese mensaje porque parece intentar cambiar mis instrucciones o acceder a "
    "información protegida. Puedo ayudarte a registrar ingresos y gastos, revisar tu saldo, tus "
    "inversiones o hacer gráficos."
)

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_INVISIBLES = re.compile(r"[​-‏ - ⁠-⁯﻿]")

# (patrón sobre texto normalizado, peso, etiqueta)
PATRONES: list[tuple[re.Pattern, float, str]] = [
    (r"\b(ignora\w*|ignore|olvida\w*|forget|omite|omitir|descarta\w*|desobedece\w*|disregard|saltate|pasa por alto)\b"
     r".{0,40}\b(instruccion\w*|reglas?|indicaciones|prompt|ordenes|instructions?|rules|directrices|"
     r"todo lo anterior|everything above|lo que te (dijeron|programaron))", 1.0, "anular_instrucciones"),
    (r"\bno (sigas|obedezcas|respetes|cumplas) (tus|las|ninguna de tus) (reglas|instrucciones|restricciones)", 1.0,
     "anular_instrucciones"),
    (r"\b(revela\w*|muestra\w*|dime|imprime|repite|ensename|escribe|copia|reveal|show|print|repeat|tell me)\b.{0,40}"
     r"\b(prompt|instrucciones (del sistema|iniciales|originales|internas|ocultas)|tus instrucciones|"
     r"tu configuracion|mensaje (del|de) sistema|reglas internas|system message|your instructions)", 1.0,
     "revelar_prompt"),
    (r"\b(system prompt|prompt (del|de) sistema|instrucciones del sistema|mensaje de sistema)\b", 0.6, "menciona_prompt"),
    (r"\b(actua|actuar|act|comportate|finge|fingir|pretend|simula|haz de cuenta|hazte pasar)\b.{0,20}"
     r"\b(como|as|que eres|ser|to be)\b", 0.5, "cambio_rol"),
    (r"\b(ahora eres|a partir de ahora (eres|seras|vas a|responde)|desde ahora eres|you are now|eres un nuevo|"
     r"nuevo rol|new role|tu verdadero (objetivo|rol)|your real (goal|role))\b", 0.8, "cambio_rol"),
    (r"\b(modo|mode)\s+(desarrollador|developer|dios|god|admin\w*|root|debug|depuracion|sin (restricciones|filtros|"
     r"censura|limites)|unrestricted|jailbreak)", 1.0, "modo_especial"),
    (r"\b(jailbreak|do anything now|sin restricciones|without restrictions|no restrictions|sin filtros)\b", 0.8,
     "modo_especial"),
    (r"(<\|im_start\|>|<\|im_end\|>|<\|system\|>|\[inst\]|\[/inst\]|<<sys>>|</?system>|</?instrucciones>|"
     r"</?mensaje_usuario>|^\s*(system|sistema|assistant|asistente|developer)\s*:|"
     r"###\s*(system|sistema|instruction|instruccion|nuevas instrucciones))", 1.0, "etiquetas_rol"),
    (r"\b(nuevas? instruccion\w*|new instructions?|instruccion\w* prioritaria|override|sobrescrib\w*|"
     r"prioridad maxima)\b", 0.8, "inyectar_instrucciones"),
    (r"\b(sin enmascarar|desenmascar\w*|sin censura|sin ocultar|sin mascara|unmask\w*|en texto plano)\b", 0.6,
     "pedir_sin_mascara"),
    (r"\b(muestra\w*|dame|dime|revela\w*|lista\w*|entrega\w*)\b.{0,30}\b(rut|tarjeta|cuenta|clave|contrasena|"
     r"datos sensibles|datos personales)\b.{0,25}\b(complet\w*|original\w*|reales?|sin)\b", 0.6, "pedir_sin_mascara"),
    (r"\b(de (otros|todos los) (usuarios|clientes)|other users|all users)\b", 0.6, "datos_terceros"),
    (r"(\bdrop\s+table\b|\bdelete\s+from\b|\btruncate\b|;\s*--|\brm\s+-rf\b|\bunion\s+select\b)", 1.0, "destructivo"),
    (r"\b(borra\w*|elimina\w*|delete|wipe|resetea\w*)\b.{0,25}\b(todo|todos|toda|la base|base de datos|"
     r"historial completo|all)\b", 0.8, "destructivo"),
    (r"\b(envia\w*|manda\w*|send|reenvia\w*|exporta\w*|sube|subir|upload)\b.{0,40}\b(datos|informacion|movimientos|"
     r"todo|data|historial)\b.{0,40}(https?://|www\.|@|correo|mail|servidor|webhook)", 1.0, "exfiltracion"),
    (r"https?://", 0.3, "url"),
    (r"\b(decodifica\w*|decode|base64|rot13)\b", 0.4, "ofuscacion"),
]
PATRONES = [(re.compile(p, re.IGNORECASE | re.MULTILINE), w, e) for p, w, e in PATRONES]
RE_BASE64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
# Sobre el texto sin espacios ni signos: atrapa "i g n o r a  l a s  i n s t r u c c i o n e s".
RE_COMPACTO = re.compile(
    r"(ignora\w{0,12}instruccion|olvida\w{0,12}instruccion|ignore\w{0,12}instruction|systemprompt|"
    r"promptdelsistema|revela\w{0,6}prompt|mododesarrollador|developermode|jailbreak)"
)
RE_DAN = re.compile(r"\bDAN\b")


@dataclass
class Evaluacion:
    puntaje: float
    bloqueado: bool
    etiquetas: list[str] = field(default_factory=list)


def normalizar(texto: str) -> str:
    t = _INVISIBLES.sub("", texto)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[ \t]+", " ", t.lower())


def _variantes(texto: str) -> list[str]:
    base = normalizar(texto)
    leet = base.translate(_LEET)
    # "i g n o r a" -> "ignora"
    juntas = re.sub(r"\b(\w) (?=\w\b)", r"\1", base)
    return list(dict.fromkeys([base, leet, juntas]))


def puntuar(texto: str, umbral: float = 1.0) -> Evaluacion:
    etiquetas: dict[str, float] = {}
    for variante in _variantes(texto):
        for patron, peso, etiqueta in PATRONES:
            if patron.search(variante):
                etiquetas[etiqueta] = max(etiquetas.get(etiqueta, 0.0), peso)
    if RE_BASE64.search(texto):
        etiquetas["ofuscacion"] = max(etiquetas.get("ofuscacion", 0.0), 0.5)
    if RE_COMPACTO.search(re.sub(r"[^a-z]", "", normalizar(texto).translate(_LEET))):
        etiquetas["ofuscacion"] = max(etiquetas.get("ofuscacion", 0.0), 1.0)
    if RE_DAN.search(texto):
        etiquetas["modo_especial"] = max(etiquetas.get("modo_especial", 0.0), 0.8)
    puntaje = round(sum(etiquetas.values()), 2)
    return Evaluacion(puntaje, puntaje >= umbral, sorted(etiquetas))


def contiene_canario(texto: str | None) -> bool:
    return bool(texto) and CANARIO.lower() in texto.lower()


def filtra_prompt(salida: str, prompt_sistema: str, ventana: int = 8) -> bool:
    """True si la salida reproduce un trozo de ≥ `ventana` palabras seguidas del prompt de sistema."""
    palabras = normalizar(prompt_sistema).split()
    salida_n = " ".join(normalizar(salida).split())
    for i in range(0, max(0, len(palabras) - ventana + 1), 2):
        if " ".join(palabras[i:i + ventana]) in salida_n:
            return True
    return False
