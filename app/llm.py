"""Cliente mínimo de Ollama (RNF-02): salida estructurada, temperatura 0, sin razonamiento visible."""
from __future__ import annotations

import json
import time

import httpx

from .config import CONFIG, Config

MODELOS_CON_RAZONAMIENTO = ("qwen3", "deepseek-r1", "gpt-oss", "magistral")


class ClienteLLM:
    def __init__(self, config: Config = CONFIG):
        self.config = config
        self._disponible: tuple[float, bool] | None = None

    def disponible(self) -> bool:
        """Consulta /api/tags (con caché de 30 s) y verifica que el modelo esté descargado."""
        ahora = time.monotonic()
        if self._disponible and ahora - self._disponible[0] < 30:
            return self._disponible[1]
        try:
            r = httpx.get(f"{self.config.ollama_url}/api/tags", timeout=3)
            nombres = {m["name"] for m in r.json().get("models", [])}
            ok = self.config.modelo in nombres or f"{self.config.modelo}:latest" in nombres
        except (httpx.HTTPError, ValueError):
            ok = False
        self._disponible = (ahora, ok)
        return ok

    def _chat(self, sistema: str, usuario: str, formato=None, max_tokens: int = 256) -> tuple[str | None, dict]:
        cuerpo = {
            "model": self.config.modelo,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": 4096},
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        }
        if formato is not None:
            cuerpo["format"] = formato
        if self.config.modelo.startswith(MODELOS_CON_RAZONAMIENTO):
            cuerpo["think"] = False
        meta = {"modelo": self.config.modelo}
        inicio = time.perf_counter()
        try:
            r = httpx.post(f"{self.config.ollama_url}/api/chat", json=cuerpo, timeout=self.config.timeout_llm)
            r.raise_for_status()
            datos = r.json()
        except (httpx.HTTPError, ValueError) as error:
            meta.update(error=str(error)[:200], latencia_ms=int((time.perf_counter() - inicio) * 1000))
            return None, meta
        meta.update(
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            tokens_prompt=datos.get("prompt_eval_count"),
            tokens_respuesta=datos.get("eval_count"),
        )
        return datos.get("message", {}).get("content", ""), meta

    def chat_json(self, sistema: str, usuario: str, esquema: dict) -> tuple[dict | None, str | None, dict]:
        """Devuelve (objeto, texto_crudo, meta). objeto es None si la salida no es JSON válido."""
        texto, meta = self._chat(sistema, usuario, formato=esquema)
        if texto is None:
            return None, None, meta
        try:
            return json.loads(texto), texto, meta
        except json.JSONDecodeError:
            meta["error"] = "json_invalido"
            return None, texto, meta

    def chat_texto(self, sistema: str, usuario: str, max_tokens: int = 220) -> tuple[str | None, dict]:
        return self._chat(sistema, usuario, max_tokens=max_tokens)
