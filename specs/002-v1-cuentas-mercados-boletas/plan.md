# Plan técnico 002 — v1 (no implementado)

Deriva de [`spec.md`](spec.md). Recoge lo que se investigó el 2026-11-24 para no repetirlo.

## 1. Arquitectura por puertos

```
app/dominio/        cálculo puro: finanzas, enmascarado, cifrado (primitivas, sobre, índice ciego)
app/puertos/        LLMPort, VisionPort, MercadoPort, BancoPort, KeyEncryptionPort, RepositorioPort
app/adaptadores/    ollama_llm, ollama_vision, mercado_<fuente>, banco_simulado, kek_archivo, postgres
app/web/            FastAPI: auth, chat, mercados, boletas
```

El dominio no conoce Ollama, Postgres ni la fuente de mercado (igual que el `SecretsPort` de EMA, que no
sabe que detrás hay OpenBao). `LLMPort` expone `chat_json(sistema, usuario, esquema)` y
`chat_texto(...)`; `VisionPort` expone `extraer_boleta(imagen, esquema)`. Las dos implementaciones de v1
usan Ollama local (`qwen3:4b` y `gemma3:4b`).

## 2. Datos de mercado: lo que se probó

| Fuente | Resultado de la prueba (2026-11-24) | Nota |
|---|---|---|
| Yahoo Finance `v8/finance/chart` (`SQM-B.SN`, `AAPL`) | **HTTP 429** sin *cookie/crumb* | no tiene API pública oficial; sus términos prohíben el uso automatizado; frágil |
| Sitio de la Bolsa de Santiago | responde una SPA ("SANTIAGOX"); `robots.txt` devuelve la misma página | los datos vienen de endpoints JSON internos; hay que revisar términos y si ofrecen API de datos |

Propuesta: `MercadoPort` con adaptadores intercambiables, caché en la tabla `precios` (`origen`, `fecha_dato`)
y un adaptador **CSV/manual** siempre disponible. Antes de implementar un adaptador de *scraping*:
revisar términos de uso, preferir una API con llave gratuita si existe, limitar a 1 petición cada pocos
segundos por fuente y nunca enviar datos del usuario (solo nemotécnicos).

## 3. Cifrado igual que EMA (`glasmed_app_backend/src/domain/cifrado`)

Se revisó el código de EMA (solo los módulos de cifrado y la documentación; ningún dato). Se replica en
Python con `cryptography`:

| Pieza | En EMA | En v1 |
|---|---|---|
| Algoritmo | AES-256-GCM, nonce 12 B, tag 16 B; HMAC-SHA256 | igual (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`, `hmac`) |
| Sobre | `0x01 ‖ dek_version (uint16 BE) ‖ nonce ‖ ciphertext ‖ tag` | igual |
| AAD | cabecera ‖ `"glasmed:campo:v1\0<tenant>\0<tabla>\0<columna>"` | cabecera ‖ `"pln:campo:v1\0<usuario uuid>\0<tabla>\0<columna>"` |
| Llaves | DEK y llave HMAC **por tenant**, versionadas, guardadas envueltas por una KEK | DEK y llave HMAC **por usuario** |
| Paquete envuelto | `0x01 ‖ uso (DEK/HMAC) ‖ tenant (16 B) ‖ versión ‖ llave` (52 B), se verifica al desenvolver | igual |
| KEK | OpenBao Transit (no sale de OpenBao) | `KeyEncryptionPort`: archivo local 0600 para la demo; OpenBao como adaptador futuro |
| Índice ciego | `HMAC(llave_hmac, etiqueta ‖ 0x00 ‖ valor canónico)`, etiqueta por uso | igual: `pln:indice:correo:v1`, `pln:indice:rut:v1` |
| Columnas | `*_cifrado` + catálogo `CAMPOS_CIFRADOS` probado contra `information_schema` | igual |
| Aislamiento | PostgreSQL con RLS, policy `tenant_isolation`, `SET LOCAL` en la transacción | policy `aislamiento_usuario` |
| Rotación | jobs de rotación y re-cifrado | fuera de v1 (se deja la versión en el sobre para poder hacerlo) |

Campos cifrados propuestos: `usuarios.nombre_cifrado`, `usuarios.correo_cifrado` (+ `correo_hmac`),
`movimientos.descripcion_cifrado`, `boletas.comercio_cifrado`, `boletas.texto_cifrado`,
`boveda.valor_cifrado` (+ `valor_hmac`), `auditoria.detalle_cifrado`. Los montos quedan en claro (como
`montoBruto` en EMA), protegidos por RLS, para poder sumarlos en SQL. El `google_sub` solo se guarda como
índice ciego con una llave global de identidad.

## 4. Boletas

1. El navegador envía la imagen (≤ 5 MB, JPEG/PNG/WebP; se revisan los *magic bytes*).
2. `VisionPort.extraer_boleta` con `gemma3:4b` y el esquema `{comercio, fecha, total, items[], categoria}`.
3. Python valida el total (suma de ítems vs total, formato CLP) y normaliza con `app/reglas.py`.
4. Enmascarado y detector de inyección sobre todo el texto extraído.
5. Pantalla de confirmación → `registrar_gasto` con `origen = 'boleta'`. La imagen se descarta de memoria.

En CPU, una imagen con un modelo de 4B puede tardar más de un minuto: la interfaz muestra el progreso.

## 5. Cuentas

OIDC de Google con `httpx` (sin SDK): `/auth/google` genera `state`, `nonce` y PKCE en una cookie firmada
de vida corta → Google → `/auth/google/callback` canjea el código en el *token endpoint* (TLS directo, como
permite OIDC) y valida `iss`, `aud`, `exp` y `nonce` del `id_token`. Se busca al usuario por
`HMAC(google_sub)`; si no existe, se crea con DEK y llave HMAC nuevas.
