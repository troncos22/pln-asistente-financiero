# Tareas 002 — v1 (pendientes, no implementadas)

Deriva de [`plan.md`](plan.md). Orden sugerido; cada tarea cita su requisito.

## Fase A — Base cifrada
- [ ] A1 Docker Compose con PostgreSQL y Ollama; roles `pln_admin` (migraciones) y `pln_app` (app) — RNF-08, RF-42
- [ ] A2 Primitivas, sobre, paquete de llave e índice ciego con vectores de prueba fijos — RF-43, RF-44, RNF-09
- [ ] A3 `KeyEncryptionPort` con adaptador de archivo local — RF-43
- [ ] A4 Migraciones: tablas con `usuario_id`, RLS forzado, columnas `*_cifrado` y `*_hmac`; prueba del catálogo — RF-42, RF-43
- [ ] A5 Repositorios con `SET LOCAL app.usuario_id`; prueba de aislamiento entre dos usuarios — RF-32, CA-10
- [ ] A6 Bóveda de datos sensibles enlazada al enmascarado (sin claves, PIN, CVV ni tarjeta completa) — RF-45

## Fase B — Cuentas
- [ ] B1 Registro con correo y contraseña, sesiones con cookie — RF-30, RF-31
- [ ] B2 Inicio de sesión con Google (OIDC + PKCE) — RF-29, CA-09

## Fase C — Puertos de modelos
- [ ] C1 `LLMPort` y migración de `app/llm.py` a adaptador Ollama — RF-40
- [ ] C2 `VisionPort` con adaptador Ollama `gemma3:4b` — RF-36, RF-40

## Fase D — Boletas
- [ ] D1 Subida/foto, validación de imagen y extracción — RF-35, RF-36
- [ ] D2 Pantalla de confirmación y registro; descarte de la imagen — RF-37, RF-39, CA-13
- [ ] D3 Enmascarado e inyección sobre el texto de la boleta; conjunto de boletas de prueba — RF-38

## Fase E — Mercados
- [ ] E1 Elegir la fuente de datos tras revisar términos de uso (pregunta abierta 2) — RF-34
- [ ] E2 `MercadoPort`, adaptador elegido, caché y límite de frecuencia — RF-34
- [ ] E3 Pantalla Mercados con tabla, gráfico y "registrar compra" — RF-33, CA-14

## Fase F — Cierre
- [ ] F1 Re-ejecutar las 84 conversaciones por usuario — RNF-10
- [ ] F2 Volcado de la base sin datos en claro — CA-11
- [ ] F3 Bitácora y prompts
