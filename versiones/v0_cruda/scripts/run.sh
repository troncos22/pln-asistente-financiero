#!/usr/bin/env bash
# Crea el entorno si falta y levanta la app en http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
exec .venv/bin/python -m app
