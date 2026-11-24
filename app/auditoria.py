"""Bitácora de auditoría de la app (RF-26). Todo se enmascara de nuevo antes de escribir (RF-17)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .masking import enmascarar_texto


def registrar(con, sesion: str, evento: str, detalle: dict, jsonl: Path | None = None) -> None:
    texto = enmascarar_texto(json.dumps(detalle, ensure_ascii=False, default=str))
    ts = datetime.now().isoformat(timespec="seconds")
    con.execute("INSERT INTO auditoria (ts, sesion, evento, detalle) VALUES (?,?,?,?)", (ts, sesion, evento, texto))
    con.commit()
    if jsonl:
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        with jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "sesion": sesion, "evento": evento, "detalle": json.loads(texto)},
                               ensure_ascii=False) + "\n")


def ultimos(con, limite: int = 50) -> list[dict]:
    filas = con.execute(
        "SELECT id, ts, sesion, evento, detalle FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)
    ).fetchall()
    return [{**dict(f), "detalle": json.loads(f["detalle"])} for f in filas]
