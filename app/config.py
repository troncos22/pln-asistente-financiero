"""Configuración del asistente (RNF-02, RNF-05, RF-04).

Todo se controla con variables de entorno para que la app, las pruebas y la evaluación
usen exactamente el mismo código con distintos parámetros.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _hoy() -> date:
    valor = os.getenv("ASISTENTE_HOY")
    return date.fromisoformat(valor) if valor else date.today()


@dataclass
class Config:
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    modelo: str = field(default_factory=lambda: os.getenv("ASISTENTE_MODELO", "qwen3:4b"))
    nlu_modo: str = field(default_factory=lambda: os.getenv("NLU_MODO", "hibrido"))  # llm | reglas | hibrido
    respuesta_modo: str = field(default_factory=lambda: os.getenv("RESPUESTA_MODO", "plantilla"))  # plantilla | llm
    umbral_inyeccion: float = field(default_factory=lambda: float(os.getenv("UMBRAL_INYECCION", "1.0")))
    timeout_llm: float = field(default_factory=lambda: float(os.getenv("TIMEOUT_LLM", "120")))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("ASISTENTE_DB", RAIZ / "data" / "finanzas.db")))
    auditoria_jsonl: Path = field(
        default_factory=lambda: Path(os.getenv("ASISTENTE_AUDITORIA", RAIZ / "data" / "auditoria.jsonl"))
    )

    @property
    def hoy(self) -> date:
        return _hoy()


CONFIG = Config()
