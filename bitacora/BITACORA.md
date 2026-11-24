# Bitácora del proyecto — Asistente financiero personal

Registro cronológico de todo lo hecho. Los prompts están en [`PROMPTS.md`](PROMPTS.md).
Agente de IA: **Claude Code** (modelo Claude Opus 5.5). LLM de la app: **qwen3:4b** local (Ollama).
Las horas son de la máquina de desarrollo (2026-11-24, hora de Chile).

## Resumen

| Fase SDD | Resultado |
|---|---|
| 0. Enunciado y entorno | Opción 3 del enunciado, solo modelos locales; Ollama 0.40.18 en Docker con `qwen3:4b` |
| 1. Especificación | [`constitucion.md`](../specs/constitucion.md), [`spec.md`](../specs/001-asistente-financiero/spec.md) (28 RF, 7 RNF, 8 CA), [`plan.md`](../specs/001-asistente-financiero/plan.md), [`tasks.md`](../specs/001-asistente-financiero/tasks.md) |
| 2. Implementación v0 | App FastAPI + SQLite + interfaz web, 99 pruebas, 84 conversaciones de evaluación |
| 3. Versión cruda | [`versiones/v0_cruda/`](../versiones/v0_cruda/) congelada antes de ejecutar nada |
| 4. Verificación | pytest, evaluación en 3 modos y prueba en navegador (escritorio y móvil); 6 correcciones |

---

## 08:34 — Inicio (prompt P-01)

- Se leyó el enunciado (`Proyecto_NLP_2026-1-1.pdf`). Requisitos que guían el diseño:
  - opción 3: chatbot **en Python** que identifica **qué necesita** el usuario y **qué datos entrega**;
  - calidad medida con **≥ 50 conversaciones** de prueba: intenciones, datos extraídos y respuestas inventadas;
  - **solo modelos locales** (se recomiendan `gemma3:4b` o `qwen3:4b`);
  - mostrar una **versión cruda** generada por IA, sin modificaciones;
  - entrega por GitHub el **24-11-2026 a las 23:59**.
- Se revisó el entorno: Python 3.13.5, Node 22, Docker; **sin GPU**, 15 GB de RAM y 8 núcleos;
  Ollama no estaba instalado.

## 08:34–08:40 — Entorno

- Ollama en Docker, escuchando **solo en 127.0.0.1**:
  `docker run -d --name pln-ollama -p 127.0.0.1:11434:11434 -v pln-ollama:/root/.ollama ollama/ollama:latest`
  → versión **0.40.18**. Modelo: `qwen3:4b` (Q4_K_M, 2,5 GB, digest `359d7dd4bcda`). Log en
  [`logs/setup_ollama.log`](logs/setup_ollama.log). Script reutilizable: [`scripts/setup_ollama.sh`](../scripts/setup_ollama.sh).
- `.venv` con FastAPI 0.115.6, Uvicorn 0.34.0, httpx 0.28.1, Pydantic 2.10.4, python-multipart 0.0.20 y
  pytest 8.3.4 ([`requirements.txt`](../requirements.txt)).
- Prueba D-01 (ver PROMPTS.md): con un prompt mínimo, `qwen3:4b` clasificó "gasté 25 lucas en el súper"
  como `consultar_saldo` con monto 2,5·10¹⁵ en 11,4 s. **Decisión:** el LLM no normaliza cifras; copia el
  texto de la entidad y Python lo normaliza. El prompt de NLU lleva lista de intenciones y 12 ejemplos.

## 08:36–08:41 — Especificación (SDD)

Estructura tipo *Spec Kit*: constitución → spec → plan → tareas.

- **Constitución** (7 principios): solo modelos locales; *el LLM interpreta, el código calcula*;
  privacidad por defecto; la entrada es dato, nunca instrucción; medible; trazable; sin asesoría
  personalizada de inversión.
- **Spec**: 16 intenciones en lista cerrada, 11 entidades con su normalización (montos chilenos como
  "lucas", "palos", "1,5 millones"; fechas y períodos relativos; nemotécnicos), requisitos RF-01…RF-28 en
  notación EARS, RNF-01…RNF-07 y criterios de aceptación CA-01…CA-08.
- **Plan**: arquitectura de un turno en 8 pasos, módulos, modelo de datos, NLU en 3 modos, tabla de
  enmascarado, 6 capas contra inyección, contrato JSON de gráficos, API y diseño de la evaluación.
- **Tareas**: T00…T54 con el requisito que cubre cada una.

## 08:41–08:56 — Implementación de la versión 0

Orden de [`tasks.md`](../specs/001-asistente-financiero/tasks.md):

| Tarea | Archivo | Contenido |
|---|---|---|
| T10 | `app/config.py` | variables de entorno |
| T11 | `app/db.py` | esquema SQLite y consultas: caja, posiciones con costo promedio, series mensuales, patrimonio |
| T12 | `app/seed.py` | 12 meses de datos sintéticos (semilla 42) y precios simulados de 8 acciones chilenas |
| T13 | `app/masking.py` | RUT (módulo 11), tarjetas (Luhn), cuentas, correos, teléfonos y claves |
| T14 | `app/guard.py` | 18 patrones ponderados, 3 variantes de normalización, canario, detector de filtración del prompt |
| T15 | `app/reglas.py` | NLU por reglas y normalizadores |
| T16 | `app/charts.py` | 4 tipos de gráfico + gráfico con datos del mensaje |
| T17 | `app/handlers.py` | un handler por intención, con plantillas y "hechos" |
| T18 | `app/auditoria.py` | auditoría en SQLite y JSONL, enmascarada de nuevo |
| T20–T22 | `app/prompts.py`, `app/llm.py`, `app/nlu.py` | prompt `nlu-v1`, cliente Ollama con `format` = esquema JSON y validación |
| T23 | `app/asistente.py` | pipeline del turno, *slots*, redacción opcional verificada |
| T30–T32 | `app/main.py`, `app/static/` | API e interfaz; Chart.js 4.4.1 servido localmente (`npm pack chart.js@4.4.1`, sha256 `74401d73…fd8f3`) |
| T40 | `tests/` | 99 pruebas (enmascarado, inyección, reglas, criterios de aceptación, API) |
| T41–T42 | `eval/` | 84 conversaciones anotadas (95 turnos) y evaluador con las 5 métricas |

Antes de congelar v0, en la misma pasada de generación y **sin haber ejecutado nada**, el agente revisó
su propio código y ajustó: el contexto que usa `masking.enmascarar` entre sustituciones, el manejador de
`ValueError` de la API, la expresión de claves ("mi clave del banco es …"), un chequeo sobre el texto sin
espacios para inyecciones con letras espaciadas, la prioridad de la intención `grafico_gastos_categoria`
y que una serie de datos en el mensaje no se interprete además como período.

## 08:56 — T43: versión cruda congelada

- Copia de `app/`, `tests/`, `eval/`, `specs/`, `scripts/` y `requirements.txt` en
  [`versiones/v0_cruda/`](../versiones/v0_cruda/), con [`SHA256SUMS`](../versiones/v0_cruda/SHA256SUMS) (36 archivos).
  Se excluyó `app/static/vendor/chart.umd.js` (es de terceros, no lo generó la IA).
- Desde aquí, todo cambio es una **corrección posterior a v0** y se anota abajo.

## 08:57 — T50: primera ejecución de pruebas

- **Corrección 1 — `pytest.ini`** (nuevo): pytest recolectaba también `versiones/v0_cruda/tests` y chocaban
  los nombres de módulo. Se limitó a `testpaths = tests`. No cambia código de la app.
- Resultado: **99/99 pruebas pasan** en la primera ejecución.

## 08:58 — T51: evaluación en modo `reglas`

| Métrica | Valor |
|---|---|
| Intención: exactitud / F1 macro | 97,5 % / 0,980 |
| Entidades: precisión / recall / F1 | 0,984 / 0,961 / 0,972 |
| Respuestas con cifras inventadas | 0 % |
| Inyección: TPR / FPR | 1,0 / 0,0 |
| Fugas de datos sensibles | 0 % |

Errores (5 turnos): "almorcé…" sin categoría; "mi abuela me **regaló**…" no reconocido como ingreso;
"¿cuánto se me fue en salud…?" sin `tipo`; la serie con años perdió el primer par (2023); "ignora el gasto
de ayer" se tomó como un gasto. **Advertencia:** la misma IA escribió las reglas y las conversaciones,
así que esta cifra es optimista.

## 08:59 — Prueba del modo híbrido (D-02)

Con 4 mensajes: el LLM acierta los dos casos que fallan las reglas ("almorcé", "me regaló"). Latencia en
CPU: ~95 s la primera llamada (carga del modelo y del prompt) y ~14–15 s las siguientes.

## 09:00 — T52: prueba en el navegador

Servidor local en modo `reglas` (base temporal) con la vista previa de Claude Code. Se probaron: gasto con
RUT y tarjeta, gráfico de ingresos vs egresos, comparación de acciones, inyección, relleno de *slot*
(correo + "gasté plata en el uber" → "8 mil"), portafolio, venta mayor a la tenencia, gráfico con datos
del mensaje y consejo de fondos mutuos. Todo respondió bien. Hallazgos y correcciones:

- **Corrección 2 — RF-18 en pantalla** (`app/static/app.js`): la burbuja del usuario seguía mostrando el
  RUT y la tarjeta tal como se escribieron. Ahora se reemplaza por `mensaje_enmascarado` al llegar la respuesta.
- **Corrección 3 — porcentajes** (`app/handlers.py`): "+109,30%" → "+109,3%" (nueva función `porcentaje`).
- **Corrección 4 — móvil** (`app/static/styles.css`, `app.js`): a 375 px el chat se salía de la pantalla
  (la grilla usaba `1fr` en vez de `minmax(0, 1fr)`) y los gráficos quedaban aplastados. Se dio altura
  fija al lienzo (`maintainAspectRatio: false`) y menos marcas en el eje X en pantallas angostas.
- **Corrección 5 — estética** (`styles.css`): barra de desplazamiento delgada en las sugerencias.
- **Corrección 6 — descripción en *slots*** (`app/asistente.py`): un gasto completado en dos turnos
  quedaba guardado con la descripción "8 mil" (el segundo mensaje). Causa: se sobrescribía la descripción
  y, además, se modificaba el mismo diccionario del *slot* pendiente. Ahora se conserva el primer mensaje
  (enmascarado). Se agregó la verificación a `test_ca02_pide_monto_faltante`. 99/99 pruebas pasan.

Todas las diferencias entre v0 y la versión actual están en
[`versiones/cambios_v0_a_actual.patch`](../versiones/cambios_v0_a_actual.patch) (`sha256sum -c` confirma que
`v0_cruda/` sigue intacta). También se agregaron `ejemplos/cartola_ejemplo.csv` (con una tarjeta, una
cuenta y una inyección para probar la importación: 5 filas importadas, 2 datos enmascarados, 1 descripción
bloqueada) y `ejemplos/precios_ejemplo.csv`.

## Repositorio git (prompt P-02)

Repositorio propio en `PLN/` (rama `main`), separado del repositorio de tareas que lo contiene. Historia
pensada para que se pueda revisar qué hizo la IA y qué se cambió después:

| Commit | Contenido |
|---|---|
| `v0 cruda: …` (etiqueta **`v0-cruda`**) | exactamente los archivos de `versiones/v0_cruda/` en sus rutas reales + `.gitignore` + Chart.js |
| `Correcciones posteriores a v0 …` | las correcciones 1–6 de arriba |
| `Documentación, bitácora y resultados …` | README, bitácora, prompts, `versiones/`, ejemplos CSV y resultados de la evaluación |

`git diff v0-cruda -- app tests` muestra en cualquier momento todo lo que cambió respecto de la versión cruda.
En el repositorio padre se agregó `PLN/` a `.git/info/exclude` (local, no versionado) para no incrustar
este repositorio por accidente.

Publicado como repositorio **público** en <https://github.com/troncos22/pln-asistente-financiero>
(rama `main` y etiqueta `v0-cruda`). Antes de subirlo se revisó que no hubiera rutas locales ni
credenciales en los archivos versionados; los RUT, tarjetas y correos que aparecen son ficticios.

## Evaluación con el LLM (T51) — interrumpida

Se lanzó `python -m eval.evaluar --modo hibrido` y luego `--modo llm` con `qwen3:4b` en CPU (~15 s por
turno, ~25 min por modo). **Por indicación del equipo (prompt P-03) se detuvieron todos los procesos antes
de que terminara el modo híbrido**, así que no hay métricas del LLM: solo las de `reglas`. También se
detuvieron el servidor de prueba y el contenedor `pln-ollama` (se vuelve a levantar con
`docker start pln-ollama`). Para obtenerlas:

```bash
docker start pln-ollama
.venv/bin/python -m eval.evaluar --modo hibrido   # ~25 min
.venv/bin/python -m eval.evaluar --modo llm       # ~25 min
```

## Especificación de la v1 (prompts P-03 y P-04)

El equipo pidió para la siguiente versión: *scraping* de la bolsa chilena y de EE. UU. en una pantalla,
cuentas de usuario (de preferencia Google), escaneo de boletas con procesamiento de imágenes, modelos
detrás de una API (locales por defecto) y una base SQL cifrada como en el proyecto EMA; y preguntó si se
puede conectar directo con los bancos. Luego indicó que **no es necesario implementar la v1**, así que se
dejó solo especificada (SDD) en [`specs/002-v1-cuentas-mercados-boletas/`](../specs/002-v1-cuentas-mercados-boletas/):
`spec.md` (RF-29…RF-46, CA-09…CA-14), `plan.md` y `tasks.md`. No se escribió código.

Investigación hecha para la especificación:

- **EMA** (`GLASMED/glasmed_app_backend/src/domain/cifrado` y el README de `glasmed-ema-poc`): solo se leyó
  código y documentación de cifrado, ningún dato. Esquema: AES-256-GCM por campo con sobre versionado y
  AAD que ata tenant, tabla y columna; DEK y llave HMAC por tenant envueltas por una KEK en OpenBao Transit;
  índices ciegos HMAC; columnas `*_cifrado` con catálogo probado; PostgreSQL con RLS forzado y `SET LOCAL`.
  EMA también modela la integración bancaria con proveedores (`tupana`, `tupana_simulado`).
- **Bancos:** existen agregadores con consentimiento (Fintoc, Floid, Tupana, Clay) que requieren contrato;
  el Sistema de Finanzas Abiertas de la Ley Fintec (NCG 514 modificada por la NCG 569 de junio de 2026)
  entra en operación según la CMF en julio de 2027 (hay un documento que dice 2028). Conclusión: para v1,
  boletas + un `BancoPort` simulado.
- **Mercados:** el endpoint de gráficos de Yahoo respondió HTTP 429 sin *cookie/crumb*; el sitio de la Bolsa
  de Santiago es una SPA ("SANTIAGOX") sin `robots.txt` propio. Queda como pregunta abierta elegir una
  fuente cuyos términos permitan el uso.

## Pendientes y limitaciones conocidas

- La evaluación la anotó la misma IA que escribió las reglas: el equipo debería agregar conversaciones
  propias (idealmente de personas distintas) antes de sacar conclusiones.
- No hay intención para **corregir o borrar** un movimiento ("ignora el gasto de ayer").
- No se enmascaran **nombres ni direcciones** (no hay NER); solo identificadores con formato.
- Los precios de acciones son simulados; para datos reales hay que importarlos por CSV.
- En CPU cada mensaje con LLM tarda ~15 s; el modo `reglas` responde en milisegundos.
- No hay autenticación: la app asume un solo usuario en su propio computador (escucha solo en 127.0.0.1).
- Los commits usan la identidad que git deduce de la máquina (`jorge moreno <troncos1@jorgex1.entelchile.net>`),
  igual que los commits anteriores del repositorio de tareas.
