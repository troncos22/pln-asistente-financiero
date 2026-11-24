"""Orquestación de la comprensión: modos `llm`, `reglas` e `hibrido` (RF-01 … RF-04, RF-20, RF-21)."""
from __future__ import annotations

import re
from datetime import date

from . import guard, prompts, reglas
from .config import CONFIG, Config
from .llm import ClienteLLM

ENTIDADES_POR_INTENCION = {
    "registrar_ingreso": {"monto", "categoria", "fecha"},
    "registrar_gasto": {"monto", "categoria", "fecha"},
    "registrar_compra": {"ticker", "cantidad", "precio", "fecha"},
    "registrar_venta": {"ticker", "cantidad", "precio", "fecha"},
    "consultar_portafolio": {"ticker"},
    "consultar_movimientos": {"tipo", "categoria", "periodo"},
    "grafico_linea_tiempo": {"metrica", "periodo", "serie"},
    "grafico_ingresos_egresos": {"periodo", "serie"},
    "grafico_comparar_acciones": {"tickers", "periodo"},
    "grafico_gastos_categoria": {"periodo", "serie"},
    "consejo_inversion": {"tema"},
}
# Entidades donde el normalizador determinista es más confiable que el LLM (modo híbrido).
PREFERIR_REGLAS = {"monto", "fecha", "periodo", "cantidad", "precio", "serie"}


def _numero(texto) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", str(texto))
    return float(m.group(0).replace(",", ".")) if m else None


def normalizar_entidades_llm(crudas: dict, intencion: str, hoy: date) -> dict:
    """Convierte los textos que copió el LLM al formato normalizado de la spec §4."""
    permitidas = ENTIDADES_POR_INTENCION.get(intencion, set())
    tipo = "ingreso" if intencion == "registrar_ingreso" else "gasto"
    e: dict = {}
    for clave, valor in (crudas or {}).items():
        if clave not in permitidas or valor in (None, "", []):
            continue
        texto = valor if isinstance(valor, str) else " ".join(map(str, valor)) if isinstance(valor, list) else str(valor)
        if clave == "monto":
            v = reglas.parse_monto(texto)
        elif clave == "precio":
            v = reglas.parse_monto(texto)
            v = float(v) if v is not None else None
        elif clave == "cantidad":
            v = _numero(texto)
        elif clave == "fecha":
            v = reglas.parse_fecha(texto, hoy)
        elif clave == "periodo":
            v = reglas.parse_periodo(texto, hoy)
        elif clave == "categoria":
            c = reglas.normalizar(texto)
            validas = reglas.CATEGORIAS_INGRESO if tipo == "ingreso" else reglas.CATEGORIAS_GASTO
            if intencion == "consultar_movimientos":
                validas = set(reglas.CATEGORIAS_GASTO) | set(reglas.CATEGORIAS_INGRESO)
            v = c if c in validas else reglas.detectar_categoria(texto, tipo)
        elif clave == "ticker":
            encontrados = reglas.detectar_tickers(texto) or [texto.strip().upper()]
            v = encontrados[0]
        elif clave == "tickers":
            lista = valor if isinstance(valor, list) else re.split(r",| y ", texto)
            v = []
            for x in lista:
                tk = (reglas.detectar_tickers(str(x)) or [str(x).strip().upper()])[0]
                if tk and tk not in v:
                    v.append(tk)
        elif clave == "metrica":
            v = reglas.normalizar(texto) if reglas.normalizar(texto) in reglas.METRICAS else reglas.detectar_metrica(texto)
        elif clave == "tipo":
            v = reglas.normalizar(texto) if reglas.normalizar(texto) in ("ingreso", "gasto") else None
        elif clave == "tema":
            v = texto.strip()[:60]
        else:
            v = None
        if v not in (None, "", []):
            e[clave] = v
    return e


class NLU:
    def __init__(self, llm: ClienteLLM | None = None, config: Config = CONFIG):
        self.config = config
        self.llm = llm or ClienteLLM(config)

    def _reglas(self, texto: str, hoy: date, fuente: str) -> dict:
        r = reglas.interpretar(texto, hoy)
        return {**r, "fuente": fuente, "sospecha_inyeccion": False, "llm": None}

    def _llamar_llm(self, texto: str) -> tuple[dict | None, dict]:
        """Llama al LLM y valida la salida (lista blanca, canario, filtración del prompt)."""
        obj, crudo, meta = self.llm.chat_json(prompts.NLU_SISTEMA, prompts.mensaje_nlu(texto), prompts.NLU_ESQUEMA)
        info = {"prompt_usuario": prompts.mensaje_nlu(texto), "salida_cruda": crudo, **meta,
                "version_prompt": prompts.VERSION_NLU}
        if obj is None:
            info["rechazo"] = meta.get("error", "sin_respuesta")
            return None, info
        if guard.contiene_canario(crudo) or guard.filtra_prompt(crudo or "", prompts.NLU_SISTEMA):
            info["rechazo"] = "canario_o_filtracion"
            return None, info
        if obj.get("intencion") not in reglas.INTENCIONES or not isinstance(obj.get("entidades", {}), dict):
            info["rechazo"] = "fuera_de_lista_blanca"
            return None, info
        return obj, info

    def interpretar(self, texto: str, hoy: date, modo: str | None = None) -> dict:
        modo = modo or self.config.nlu_modo
        if modo == "reglas":
            return self._reglas(texto, hoy, "reglas")
        if not self.llm.disponible():
            return self._reglas(texto, hoy, "reglas (LLM no disponible)")
        obj, info = self._llamar_llm(texto)
        if obj is None:
            r = self._reglas(texto, hoy, f"reglas (LLM inválido: {info.get('rechazo')})")
            r["llm"] = info
            return r
        intencion = obj["intencion"]
        entidades_llm = normalizar_entidades_llm(obj.get("entidades", {}), intencion, hoy)
        if modo == "llm":
            entidades = entidades_llm
        else:
            entidades_reglas = reglas.extraer_entidades(texto, intencion, hoy)
            entidades = dict(entidades_llm)
            for clave, valor in entidades_reglas.items():
                if clave in PREFERIR_REGLAS or clave not in entidades:
                    entidades[clave] = valor
        return {
            "intencion": intencion,
            "entidades": entidades,
            "fuente": modo,
            "sospecha_inyeccion": bool(obj.get("sospecha_inyeccion")),
            "llm": info,
        }
