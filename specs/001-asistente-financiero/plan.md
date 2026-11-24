# Plan técnico 001 — Asistente financiero personal

Deriva de [`spec.md`](spec.md). Cada decisión indica el requisito que atiende.

## 1. Arquitectura

```
Navegador (HTML + JS + Chart.js local)
        │  POST /api/chat {sesion_id, mensaje}
        ▼
FastAPI (app/main.py)
        │
        ▼
Pipeline de un turno (app/asistente.py)
  1. enmascarar entrada ............ app/masking.py     RF-16, RF-17
  2. detector de inyección ......... app/guard.py       RF-19
       └─ bloqueado → respuesta fija + auditoría        RF-23, RF-26
  3. ¿slot pendiente en la sesión? → completar          RF-03
  4. NLU (llm | reglas | hibrido) .. app/nlu.py         RF-01, RF-02, RF-04
       ├─ LLM: app/llm.py (Ollama /api/chat, JSON schema, canario)  RF-20, RF-21
       └─ reglas: app/reglas.py (regex + diccionarios + normalizadores)
  5. ejecutar intención ............ app/handlers.py    RF-05 … RF-14
       ├─ consultas SQL ............ app/db.py
       └─ especificación de gráfico  app/charts.py      RF-15
  6. redactar respuesta (plantilla; LLM opcional con verificación de cifras)  P2
  7. enmascarar salida ............. app/masking.py     RF-18
  8. auditoría ..................... app/auditoria.py   RF-26
        │
        ▼
SQLite data/finanzas.db         Ollama (Docker, 127.0.0.1:11434)
```

**Decisión clave (P2):** el LLM nunca produce cifras para el usuario. Devuelve un JSON con
`intencion` y `entidades`; Python valida, normaliza, calcula y arma la respuesta con plantillas.
El modo de redacción LLM (`RESPUESTA_MODO=llm`) es opcional y su salida se verifica: si contiene un
número que no está en los hechos calculados ni en el mensaje del usuario, se descarta y se usa la
plantilla. Así las "respuestas inventadas" se pueden medir y controlar.

## 2. Módulos

| Archivo | Responsabilidad | Requisitos |
|---------|-----------------|------------|
| `app/config.py` | variables de entorno: modelo, URL de Ollama, modos, fecha "hoy", rutas | RF-04, RNF-02, RNF-05 |
| `app/db.py` | esquema SQLite, inserciones y consultas agregadas | RF-05 … RF-13 |
| `app/seed.py` | datos sintéticos reproducibles (semilla fija) | RF-27 |
| `app/masking.py` | detección y enmascarado de datos sensibles | RF-16 … RF-18 |
| `app/guard.py` | puntaje de inyección, normalización, canario, verificación de salida | RF-19 … RF-23 |
| `app/reglas.py` | NLU por reglas y normalizadores (monto, fecha, período, ticker, categoría, series) | RF-01, RF-02, RF-14 |
| `app/prompts.py` | prompts de sistema versionados (NLU, redacción, consejo) | RF-20, RF-21 |
| `app/llm.py` | cliente Ollama (httpx), salida estructurada, `think: false`, timeout | RNF-02 |
| `app/nlu.py` | orquesta modos `llm`, `reglas`, `hibrido`; valida contra lista blanca | RF-01 … RF-04 |
| `app/charts.py` | especificaciones de gráfico | RF-10 … RF-15 |
| `app/handlers.py` | una función por intención; devuelve texto, hechos, gráfico, slot pendiente | RF-05 … RF-14 |
| `app/asistente.py` | pipeline del turno y estado de sesión | todos |
| `app/auditoria.py` | bitácora de auditoría (tabla + JSONL) | RF-26 |
| `app/main.py` | API REST y archivos estáticos | RF-24 |
| `app/static/` | interfaz web | RF-24, RF-25 |
| `eval/` | conversaciones anotadas y evaluador | RF-28 |
| `tests/` | pruebas unitarias y de API | RNF-06 |

## 3. Modelo de datos (SQLite)

```sql
movimientos(id, fecha TEXT, tipo TEXT CHECK(tipo IN ('ingreso','gasto')), monto INTEGER,
            categoria TEXT, descripcion TEXT, origen TEXT)          -- origen: chat|csv|demo
operaciones(id, fecha TEXT, tipo TEXT CHECK(tipo IN ('compra','venta')), ticker TEXT,
            cantidad REAL, precio REAL, origen TEXT)
precios(fecha TEXT, ticker TEXT, precio REAL, origen TEXT, PRIMARY KEY(fecha, ticker))
auditoria(id, ts TEXT, sesion TEXT, evento TEXT, detalle TEXT)     -- detalle: JSON enmascarado
```

- Caja = Σ ingresos − Σ gastos − Σ(compras·precio) + Σ(ventas·precio) (RF-07).
- Patrimonio(t) = caja(t) + Σ cantidad(t)·precio(t) por ticker (RF-10).
- Costo promedio por ticker: promedio ponderado de compras; la venta reduce cantidad sin cambiar el costo promedio (RF-08).

## 4. NLU

### 4.1 Modo `llm`
- Ollama `/api/chat`, `stream: false`, `think: false`, `options.temperature = 0`,
  `format` = esquema JSON con `intencion` ∈ enum de §4 del spec y `entidades` como objeto con
  campos opcionales de tipo string/number/array.
- Prompt de sistema (`prompts.NLU_SISTEMA`): rol, lista de intenciones con descripción, entidades,
  reglas de normalización, 10 ejemplos *few-shot* y regla de seguridad. Contiene el canario.
- El mensaje (ya enmascarado) va como `<mensaje_usuario>…</mensaje_usuario>` con la instrucción de
  tratarlo solo como dato.
- Salida: se parsea JSON; si falla el esquema, la intención no está en la lista blanca o aparece
  el canario → se descarta (fuente `llm_invalido`) y se usa `reglas`.

### 4.2 Modo `reglas`
- Normalización: minúsculas, sin acentos, espacios colapsados.
- Intención: patrones regex ordenados por prioridad (gráfico > registro > consulta > charla).
- Entidades: normalizadores deterministas (montos con "lucas", "mil", "palos", "millones";
  fechas relativas y absolutas; períodos; tickers por diccionario de alias; categorías por
  diccionario de palabras clave; series "etiqueta valor").

### 4.3 Modo `hibrido` (por defecto)
La intención la decide el LLM; las entidades se toman del LLM pero se **re-normalizan** con los
normalizadores de reglas (p. ej. "25 lucas" → 25000) y se completan con lo que encuentren las reglas
si el LLM las omitió. Si el LLM no responde, todo cae a `reglas`.

## 5. Enmascarado (RF-16 … RF-18)

| Tipo | Detección | Reemplazo |
|------|-----------|-----------|
| RUT | `\d{1,2}.?\d{3}.?\d{3}-[\dkK]` + dígito verificador módulo 11 | `[RUT]` |
| Tarjeta | 13–19 dígitos con espacios/guiones + Luhn, o precedido por "tarjeta" | `[TARJETA ****1234]` |
| Cuenta | "cuenta (corriente\|vista\|rut\|de ahorro)? (n°\|nro\|número)?" + 6–20 dígitos | `[CUENTA ****4567]` |
| Correo | regex estándar | `[CORREO]` |
| Teléfono | `(+56)? 9 dddd dddd` | `[TELEFONO]` |
| Clave | "(clave\|contraseña\|password\|pin\|cvv\|cvc) (es\|:)? valor" | `[CLAVE]` |

Los montos (`$1.200.000`, `25000`) **no** se enmascaran: son necesarios para la función.
El resultado incluye la lista de tipos encontrados (sin valores) para la interfaz y la auditoría.

## 6. Defensa contra inyección (RF-19 … RF-23)

Capas:
1. **Detector** (`guard.puntuar`): normaliza (NFKD, sin acentos, sin caracteres invisibles,
   *leetspeak* básico) y suma pesos de patrones: anular instrucciones, revelar prompt, cambio de
   rol, modos especiales/jailbreak, etiquetas de rol (`<|im_start|>`, `[INST]`, `system:`),
   pedir datos sin enmascarar, acciones destructivas (`drop table`, "borra todos los datos"),
   exfiltración (URLs, "envía mis datos a"). Umbral configurable (por defecto 1.0).
2. **Delimitación** del mensaje y declaración explícita de que es dato.
3. **Salida estructurada** con intenciones en lista blanca: aunque una inyección pase, el LLM
   solo puede elegir una intención permitida; no hay herramientas destructivas.
4. **Canario** en el prompt de sistema; si aparece en la salida se descarta.
5. **Verificación de salida**: enmascarado de la respuesta y descarte de redacciones con cifras
   no fundamentadas.
6. **Datos importados**: el CSV se enmascara y se puntúa; filas sospechosas se importan con la
   descripción reemplazada por `[DESCRIPCION BLOQUEADA]`.

## 7. Gráficos (RF-10 … RF-15)

Contrato: `{"tipo": "line|bar|doughnut", "titulo": str, "etiquetas": [str], "series":
[{"nombre": str, "datos": [number], "tipo": "line|bar"?}], "unidad": "CLP|base 100|acciones",
"nota": str?}`. El frontend lo traduce a Chart.js. Series mensuales (`AAAA-MM`) salvo acciones
(semanales para períodos > 3 meses, diarias si no).

Datos en línea (RF-14): si el mensaje trae ≥ 2 pares `etiqueta valor`, el gráfico los usa.

## 8. API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | interfaz |
| GET | `/api/estado` | modelo, disponibilidad del LLM, modos, fecha hoy |
| POST | `/api/chat` | `{sesion_id, mensaje}` → `{respuesta, intencion, entidades, grafico, bloqueado, enmascarados, puntaje_inyeccion, fuente_nlu, latencia_ms}` |
| GET | `/api/resumen` | caja, patrimonio, ingresos y gastos del mes |
| GET | `/api/movimientos?limite=` | últimos movimientos |
| GET | `/api/portafolio` | posiciones |
| POST | `/api/importar/movimientos` | CSV `fecha,tipo,monto,categoria,descripcion` |
| POST | `/api/importar/precios` | CSV `fecha,ticker,precio` |
| GET | `/api/auditoria?limite=` | últimos eventos |

El servidor escucha solo en `127.0.0.1` (RF-24).

## 9. Evaluación (RF-28)

- `eval/conversaciones.jsonl`: una conversación por línea, con turnos anotados:
  `{"id", "categoria", "turnos": [{"usuario", "intencion", "entidades", "bloqueado",
  "no_debe_contener": [...], "debe_contener": [...]}]}`.
- `eval/evaluar.py --modo {reglas,llm,hibrido}`: cada conversación corre sobre una base temporal
  sembrada con la misma semilla y `ASISTENTE_HOY=2026-11-24`.
- Métricas:
  - intención: exactitud y F1 macro;
  - entidades: precisión, recall y F1 por par (entidad, valor) normalizado;
  - respuestas inventadas: % de respuestas con algún número no presente en los hechos del handler
    ni en el mensaje del usuario, más violaciones de `debe_contener` / `no_debe_contener`;
  - inyección: TPR sobre turnos con `bloqueado: true`, FPR sobre el resto;
  - fugas: % de turnos donde un valor sensible original aparece en la respuesta, la base, la
    auditoría o el prompt enviado al LLM.
- Salida: `eval/resultados/<modo>.json` y `eval/resultados/<modo>.md`.

## 10. Versionado y trazabilidad (P6)

- `versiones/v0_cruda/`: copia exacta del código tal como lo generó la IA, antes de ejecutar
  pruebas o corregir nada, con `SHA256SUMS`.
- Toda corrección posterior se anota en `bitacora/BITACORA.md` con motivo y archivos.
- Prompts: `bitacora/PROMPTS.md` (usuario → agente) y `app/prompts.py` (sistema → LLM).
