"""Pipeline de un turno de conversación (plan §1)."""
from __future__ import annotations

import json
import re
import time

from . import auditoria, guard, handlers, masking, prompts, reglas
from .config import CONFIG, Config
from .llm import ClienteLLM
from .nlu import NLU
from .verificacion import cifras_no_fundamentadas

LARGO_MAXIMO = 2000


class Asistente:
    def __init__(self, con, config: Config = CONFIG, llm: ClienteLLM | None = None):
        self.con = con
        self.config = config
        self.llm = llm or ClienteLLM(config)
        self.nlu = NLU(self.llm, config)
        self.sesiones: dict[str, dict] = {}

    # ------------------------------------------------------------ slots (RF-03)
    def _completar(self, pendiente: dict, texto: str, hoy) -> dict | None:
        intencion_nueva = reglas.detectar_intencion(texto)
        if intencion_nueva not in ("fuera_de_dominio", pendiente["intencion"]):
            return None  # el usuario cambió de tema
        e = dict(pendiente["entidades"])
        falta = pendiente["falta"]
        valor = None
        if falta == "monto":
            valor = reglas.parse_monto(texto)
        elif falta == "ticker":
            valor = (reglas.detectar_tickers(texto) or [None])[0]
        elif falta == "cantidad":
            valor = reglas.parse_cantidad(texto)
            if valor is None and (m := re.search(r"\d+(?:[.,]\d+)?", texto)):
                valor = float(m.group(0).replace(",", "."))
        elif falta == "precio":
            v = reglas.parse_monto(texto)
            valor = float(v) if v else None
        if valor in (None, 0):
            return None
        e[falta] = valor
        extra = reglas.extraer_entidades(texto, pendiente["intencion"], hoy)
        for clave, v in extra.items():
            e.setdefault(clave, v)
        return {"intencion": pendiente["intencion"], "entidades": e, "fuente": "slot", "sospecha_inyeccion": False,
                "llm": None}

    # ------------------------------------------------------------ redacción opcional con LLM
    def _redactar(self, res: handlers.Resultado, mensaje: str) -> tuple[str, str]:
        if not self.llm.disponible():
            return res.texto, "plantilla (LLM no disponible)"
        entrada = f"RESPUESTA BASE:\n{res.texto}\n\nHECHOS:\n{json.dumps(res.hechos, ensure_ascii=False, default=str)}"
        texto, _ = self.llm.chat_texto(prompts.REDACCION_SISTEMA, entrada)
        if not texto or guard.contiene_canario(texto):
            return res.texto, "plantilla (redacción rechazada)"
        if cifras_no_fundamentadas(texto, res.hechos, mensaje, res.texto):
            return res.texto, "plantilla (redacción con cifras no fundamentadas)"
        return texto.strip(), "llm"

    def _consejo_llm(self, res: handlers.Resultado, mensaje: str) -> tuple[str, str]:
        if not self.llm.disponible():
            return res.texto, "plantilla (LLM no disponible)"
        texto, _ = self.llm.chat_texto(prompts.CONSEJO_SISTEMA, prompts.mensaje_nlu(mensaje))
        if not texto or guard.contiene_canario(texto) or cifras_no_fundamentadas(texto, {}, mensaje):
            return res.texto, "plantilla (consejo rechazado)"
        return f"{texto.strip()}\n\n{handlers.DESCARGO}", "llm"

    # ------------------------------------------------------------ turno
    def procesar(self, sesion_id: str, mensaje: str, modo: str | None = None) -> dict:
        inicio = time.perf_counter()
        hoy = self.config.hoy
        sesion = self.sesiones.setdefault(sesion_id, {"pendiente": None, "turnos": 0})
        sesion["turnos"] += 1

        m = masking.enmascarar(mensaje[:LARGO_MAXIMO])
        ev = guard.puntuar(m.texto, self.config.umbral_inyeccion)
        salida = {"mensaje_enmascarado": m.texto, "enmascarados": m.tipos, "puntaje_inyeccion": ev.puntaje,
                  "etiquetas_inyeccion": ev.etiquetas, "bloqueado": False, "grafico": None, "hechos": {},
                  "prompt_llm": None, "salida_llm": None, "redaccion": "plantilla"}

        if ev.bloqueado:
            sesion["pendiente"] = None
            salida.update(respuesta=guard.RESPUESTA_BLOQUEO, intencion=None, entidades={}, bloqueado=True,
                          fuente_nlu="guard")
            return self._cerrar(sesion_id, salida, inicio, "bloqueo")

        interp = None
        if sesion["pendiente"]:
            interp = self._completar(sesion["pendiente"], m.texto, hoy)
            sesion["pendiente"] = None
        if interp is None:
            interp = self.nlu.interpretar(m.texto, hoy, modo)
        if interp.get("llm"):
            salida.update(prompt_llm=interp["llm"].get("prompt_usuario"), salida_llm=interp["llm"].get("salida_cruda"))

        if interp["sospecha_inyeccion"] and ev.puntaje >= 0.3:  # dos capas coinciden
            salida.update(respuesta=guard.RESPUESTA_BLOQUEO, intencion=interp["intencion"],
                          entidades=interp["entidades"], bloqueado=True, fuente_nlu=interp["fuente"])
            return self._cerrar(sesion_id, salida, inicio, "bloqueo")

        intencion, entidades = interp["intencion"], dict(interp["entidades"])
        if intencion in ("registrar_gasto", "registrar_ingreso"):
            entidades["descripcion"] = m.texto[:120]
        res = handlers.ejecutar(self.con, intencion, entidades, hoy, sesion)
        if res.pendiente:
            sesion["pendiente"] = res.pendiente

        texto, redaccion = res.texto, "plantilla"
        if intencion == "consejo_inversion" and self.config.respuesta_modo == "llm":
            texto, redaccion = self._consejo_llm(res, m.texto)
        elif self.config.respuesta_modo == "llm" and not res.pendiente:
            texto, redaccion = self._redactar(res, m.texto)

        entidades.pop("descripcion", None)
        salida.update(respuesta=masking.enmascarar_texto(texto), intencion=intencion, entidades=entidades,
                      fuente_nlu=interp["fuente"], grafico=res.grafico, hechos=res.hechos, redaccion=redaccion,
                      pendiente=(res.pendiente or {}).get("falta"), accion=res.accion)
        return self._cerrar(sesion_id, salida, inicio, "turno")

    def _cerrar(self, sesion_id: str, salida: dict, inicio: float, evento: str) -> dict:
        salida["latencia_ms"] = int((time.perf_counter() - inicio) * 1000)
        detalle = {k: salida.get(k) for k in ("mensaje_enmascarado", "intencion", "entidades", "fuente_nlu",
                                              "enmascarados", "puntaje_inyeccion", "etiquetas_inyeccion",
                                              "bloqueado", "prompt_llm", "salida_llm", "respuesta", "redaccion",
                                              "latencia_ms")}
        auditoria.registrar(self.con, sesion_id, evento, detalle, self.config.auditoria_jsonl)
        return salida
