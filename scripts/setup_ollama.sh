#!/usr/bin/env bash
# Levanta Ollama en Docker (solo en 127.0.0.1) y descarga el modelo local.
set -euo pipefail
MODELO="${1:-qwen3:4b}"
if ! docker ps -a --format '{{.Names}}' | grep -qx pln-ollama; then
  docker run -d --name pln-ollama --restart unless-stopped -p 127.0.0.1:11434:11434 -v pln-ollama:/root/.ollama ollama/ollama:latest
fi
docker start pln-ollama >/dev/null
until curl -s http://127.0.0.1:11434/api/version >/dev/null; do sleep 1; done
docker exec pln-ollama ollama pull "$MODELO"
