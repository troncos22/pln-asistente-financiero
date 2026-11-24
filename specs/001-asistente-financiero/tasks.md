# Tareas 001 — Asistente financiero personal

Deriva de [`plan.md`](plan.md). Estado: `[ ]` pendiente, `[x]` hecha. `[P]` = puede hacerse en paralelo.

## Fase 0 — Preparación
- [x] T00 Leer el enunciado y fijar el alcance (opción 3, modelo local) — P1
- [x] T01 Escribir constitución, spec, plan y tareas — P6
- [x] T02 Levantar Ollama local (Docker) y descargar `qwen3:4b` — RNF-02
- [x] T03 Entorno Python (`.venv`, `requirements.txt`) — RNF-01

## Fase 1 — Núcleo sin LLM
- [x] T10 `config.py` (variables de entorno, fecha hoy) — RNF-05
- [x] T11 `db.py` esquema y consultas (caja, portafolio, agregados mensuales, patrimonio) — RF-05…RF-13
- [x] T12 `seed.py` datos sintéticos reproducibles — RF-27
- [x] T13 [P] `masking.py` — RF-16…RF-18
- [x] T14 [P] `guard.py` — RF-19, RF-21, RF-23
- [x] T15 [P] `reglas.py` NLU por reglas y normalizadores — RF-01, RF-02, RF-14
- [x] T16 `charts.py` — RF-10…RF-15
- [x] T17 `handlers.py` — RF-03, RF-05…RF-14, P7
- [x] T18 `auditoria.py` — RF-26

## Fase 2 — LLM
- [x] T20 `prompts.py` (NLU con few-shot y canario, redacción, consejo) — RF-20, RF-21
- [x] T21 `llm.py` cliente Ollama con salida estructurada — RNF-02
- [x] T22 `nlu.py` modos `llm`/`reglas`/`hibrido` y lista blanca — RF-01…RF-04, RF-20
- [x] T23 `asistente.py` pipeline del turno, sesión y slots — todos

## Fase 3 — Web
- [x] T30 `main.py` API REST, solo 127.0.0.1 — RF-24
- [x] T31 Frontend: chat, gráficos, panel, importación, auditoría, detalle NLU — RF-24, RF-25
- [x] T32 Chart.js servido localmente — RNF-04

## Fase 4 — Calidad
- [x] T40 `tests/` unitarias (masking, guard, reglas, handlers) y de API — RNF-06, CA-07
- [x] T41 `eval/conversaciones.jsonl` ≥ 50 conversaciones anotadas — RF-28
- [x] T42 `eval/evaluar.py` con las 5 métricas — RF-28, CA-08
- [x] T43 Congelar `versiones/v0_cruda/` + `SHA256SUMS` antes de ejecutar nada — P6

## Fase 5 — Verificación y documentación
- [x] T50 Ejecutar pytest y corregir (cada corrección en la bitácora)
- [ ] T51 Ejecutar evaluación en modo `reglas` e `hibrido` (`reglas` hecha; `hibrido` y `llm` interrumpidas)
- [x] T52 Probar la app en el navegador (CA-01…CA-06)
- [x] T53 README con instalación y uso
- [x] T54 Cerrar bitácora y prompts
