# Asistente financiero personal — Proyecto PLN 2026 (opción 3)

Chatbot en Python que atiende las consultas de una persona sobre **su dinero y sus inversiones**:
entiende qué necesita (intención) y qué datos entrega (entidades), registra ingresos, gastos y
operaciones con acciones, responde saldos y resúmenes calculados y **dibuja gráficos** (línea de tiempo,
ingresos vs egresos, comparación de acciones y gastos por categoría). Corre **localmente** como app web,
usa un **LLM local** (Ollama + `qwen3:4b`), **enmascara los datos sensibles** y tiene **defensas contra
prompt injection**.

Se desarrolló con **Spec-Driven Development (SDD)**: primero la especificación y después el código.
Ver [`specs/`](specs/) y la bitácora en [`bitacora/`](bitacora/).

## Inicio rápido

```bash
# 1. LLM local (Docker). Descarga ~2,5 GB la primera vez.
./scripts/setup_ollama.sh qwen3:4b

# 2. App web en http://127.0.0.1:8000 (crea .venv si no existe)
./scripts/run.sh
```

Sin Ollama, la app funciona igual en modo `reglas` (avisa en la barra superior).

Variables de entorno útiles:

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `NLU_MODO` | `hibrido` | `llm`, `reglas` o `hibrido` (LLM decide la intención y las reglas normalizan las entidades) |
| `RESPUESTA_MODO` | `plantilla` | `llm` redacta con el modelo y descarta lo que traiga cifras inventadas |
| `ASISTENTE_MODELO` | `qwen3:4b` | p. ej. `gemma3:4b` (antes: `./scripts/setup_ollama.sh gemma3:4b`) |
| `ASISTENTE_HOY` | fecha del sistema | fija "hoy" (la evaluación usa `2026-11-24`) |
| `ASISTENTE_DB` | `data/finanzas.db` | base SQLite |
| `UMBRAL_INYECCION` | `1.0` | puntaje desde el que se bloquea un mensaje |

Para volver a cargar los datos de ejemplo: `.venv/bin/python -m app.seed --reset`.

## Qué se puede escribir

| Ejemplo | Intención |
|---|---|
| gasté 25 lucas en el súper ayer | `registrar_gasto` |
| me pagaron el sueldo, 1.850.000 | `registrar_ingreso` |
| compré 10 acciones de SQM-B a $41.000 | `registrar_compra` |
| ¿cuánta plata tengo? | `consultar_saldo` |
| ¿cómo van mis acciones de Falabella? | `consultar_portafolio` |
| ¿cuánto gasté en transporte el mes pasado? | `consultar_movimientos` |
| ¿cómo ha evolucionado mi patrimonio este año? | `grafico_linea_tiempo` |
| gráfico de ingresos vs gastos de los últimos 6 meses | `grafico_ingresos_egresos` |
| compara SQM-B y Falabella este año | `grafico_comparar_acciones` |
| ¿en qué se me va la plata? | `grafico_gastos_categoria` |
| grafica mis ingresos: enero 1.200.000, febrero 980.000, marzo 1.050.000 | gráfico con los datos del mensaje |

Si falta un dato obligatorio (p. ej. el monto), el asistente lo pregunta y completa el registro en el
turno siguiente. También se puede importar una cartola CSV (`fecha,tipo,monto,categoria,descripcion`) y
precios (`fecha,ticker,precio`) desde la pestaña **Importar**.

> Los movimientos y precios de ejemplo son **sintéticos** (precios simulados con un paseo aleatorio).
> El asistente no da recomendaciones personalizadas de inversión.

## Arquitectura

```
mensaje ─► enmascarado ─► detector de inyección ─► NLU (LLM / reglas / híbrido) ─► handler (SQL)
                                    │ bloqueado                                        │
                                    ▼                                                  ▼
                             respuesta fija                         plantilla + hechos + gráfico JSON
                                                                                       │
                                               auditoría (enmascarada) ◄── enmascarado de salida
```

- **El LLM interpreta, el código calcula.** El modelo solo devuelve un JSON con la intención y el
  texto de cada entidad; Python normaliza ("25 lucas" → 25000), consulta SQLite y arma la respuesta.
  Por eso las cifras no pueden ser inventadas, y además se verifica automáticamente
  ([`app/verificacion.py`](app/verificacion.py)).
- **Privacidad** ([`app/masking.py`](app/masking.py)): RUT (con dígito verificador), tarjetas (Luhn),
  cuentas, correos, teléfonos y claves se reemplazan antes de llegar al LLM, a la base o a la bitácora.
- **Prompt injection** ([`app/guard.py`](app/guard.py) y [`app/nlu.py`](app/nlu.py)): detector de patrones
  ES/EN con normalización (acentos, *leetspeak*, caracteres invisibles, letras espaciadas), mensaje
  delimitado como dato, salida JSON con intenciones en lista blanca, canario en el prompt de sistema,
  detección de filtración del prompt y verificación de la salida. Los CSV importados pasan por las mismas
  defensas.

| Archivo | Rol |
|---|---|
| `app/main.py` | API FastAPI e interfaz (escucha solo en 127.0.0.1) |
| `app/asistente.py` | pipeline del turno, sesión y relleno de *slots* |
| `app/nlu.py`, `app/llm.py`, `app/prompts.py` | comprensión con LLM local |
| `app/reglas.py` | NLU por reglas y normalizadores (montos chilenos, fechas, períodos, tickers) |
| `app/handlers.py`, `app/charts.py`, `app/db.py` | lógica financiera y gráficos |
| `app/masking.py`, `app/guard.py`, `app/verificacion.py`, `app/auditoria.py` | privacidad y seguridad |
| `app/static/` | interfaz web (Chart.js 4.4.1 servido localmente) |

## Calidad

```bash
.venv/bin/python -m pytest                      # 99 pruebas, no necesitan Ollama
.venv/bin/python -m eval.evaluar --modo reglas  # evaluación sin LLM (< 1 s)
.venv/bin/python -m eval.evaluar --modo hibrido # con qwen3:4b (~20 min en CPU)
```

La evaluación usa **84 conversaciones anotadas** (95 turnos) en
[`eval/conversaciones.jsonl`](eval/conversaciones.jsonl) y mide: exactitud y F1 macro de intención,
precisión/recall/F1 de entidades, % de respuestas con cifras inventadas, TPR/FPR de inyección y % de
fugas de datos sensibles (en respuesta, mensaje al LLM, base y auditoría). Los reportes quedan en
[`eval/resultados/`](eval/resultados/).

> El conjunto de evaluación lo escribió la misma IA que escribió las reglas, así que los números del
> modo `reglas` probablemente son optimistas. Conviene que el equipo agregue conversaciones propias.

## Versiones

- [`versiones/v0_cruda/`](versiones/v0_cruda/): la primera versión **tal como la generó la IA**,
  congelada antes de ejecutar nada (`SHA256SUMS` incluido). Es la "versión cruda" que pide el enunciado.
- El código en `app/` es la versión actual. Cada diferencia con v0 está explicada en
  [`bitacora/BITACORA.md`](bitacora/BITACORA.md).
