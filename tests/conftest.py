"""Las pruebas no necesitan Ollama (RNF-06): se apunta a un puerto cerrado y se usa el modo reglas."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="asistente_test_"))
os.environ.update({
    "ASISTENTE_HOY": "2026-11-24",
    "ASISTENTE_DB": str(_TMP / "app.db"),
    "ASISTENTE_AUDITORIA": str(_TMP / "auditoria.jsonl"),
    "NLU_MODO": "reglas",
    "OLLAMA_URL": "http://127.0.0.1:9",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import db, seed  # noqa: E402
from app.asistente import Asistente  # noqa: E402
from app.config import Config  # noqa: E402


@pytest.fixture
def con():
    c = db.conectar(":memory:")
    seed.sembrar(c)
    return c


@pytest.fixture
def asistente(con, tmp_path):
    cfg = Config(nlu_modo="reglas", auditoria_jsonl=tmp_path / "auditoria.jsonl")
    return Asistente(con, cfg)
