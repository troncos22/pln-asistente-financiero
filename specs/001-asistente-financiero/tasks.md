# Tareas 001 — Asistente financiero personal

Deriva de [`plan.md`](plan.md). Estado: `[ ]` pendiente, `[x]` hecha. `[P]` = puede hacerse en paralelo.

## Fase 0 — Preparación
- [x] T00 Leer el enunciado y fijar el alcance (opción 3, modelo local) — P1
- [x] T01 Escribir constitución, spec, plan y tareas — P6
- [x] T02 Levantar Ollama local (Docker) y descargar `qwen3:4b` — RNF-02
- [x] T03 Entorno Python (`.venv`, `requirements.txt`) — RNF-01

## Fase 1 — Núcleo sin LLM
- [ ] T10 `config.py` (variables de entorno, fecha hoy) — RNF-05
- [ ] T11 `db.py` esquema y consultas (caja, portafolio, agregados mensuales, patrimonio) — RF-05…RF-13
- [ ] T12 `seed.py` datos sintéticos reproducibles — RF-27
- [ ] T13 [P] `masking.py` — RF-16…RF-18
- [ ] T14 [P] `guard.py` — RF-19, RF-21, RF-23
- [ ] T15 [P] `reglas.py` NLU por reglas y normalizadores — RF-01, RF-02, RF-14
- [ ] T16 `charts.py` — RF-10…RF-15
- [ ] T17 `handlers.py` — RF-03, RF-05…RF-14, P7
- [ ] T18 `auditoria.py` — RF-26

## Fase 2 — LLM
- [ ] T20 `prompts.py` (NLU con few-shot y canario, redacción, consejo) — RF-20, RF-21
- [ ] T21 `llm.py` cliente Ollama con salida estructurada — RNF-02
- [ ] T22 `nlu.py` modos `llm`/`reglas`/`hibrido` y lista blanca — RF-01…RF-04, RF-20
- [ ] T23 `asistente.py` pipeline del turno, sesión y slots — todos

## Fase 3 — Web
- [ ] T30 `main.py` API REST, solo 127.0.0.1 — RF-24
- [ ] T31 Frontend: chat, gráficos, panel, importación, auditoría, detalle NLU — RF-24, RF-25
- [ ] T32 Chart.js servido localmente — RNF-04

## Fase 4 — Calidad
- [ ] T40 `tests/` unitarias (masking, guard, reglas, handlers) y de API — RNF-06, CA-07
- [ ] T41 `eval/conversaciones.jsonl` ≥ 50 conversaciones anotadas — RF-28
- [ ] T42 `eval/evaluar.py` con las 5 métricas — RF-28, CA-08
- [ ] T43 Congelar `versiones/v0_cruda/` + `SHA256SUMS` antes de ejecutar nada — P6

## Fase 5 — Verificación y documentación
- [ ] T50 Ejecutar pytest y corregir (cada corrección en la bitácora)
- [ ] T51 Ejecutar evaluación en modo `reglas` e `hibrido`
- [ ] T52 Probar la app en el navegador (CA-01…CA-06)
- [ ] T53 README con instalación y uso
- [ ] T54 Cerrar bitácora y prompts
