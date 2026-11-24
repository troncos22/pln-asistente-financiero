# Especificación 002 — v1: cuentas, mercados, boletas y base cifrada

- **Estado:** especificada, **no implementada** (decisión del equipo, 2026-11-24). Este documento deja
  fijados los requisitos para cuando se retome.
- **Base:** [`001-asistente-financiero`](../001-asistente-financiero/spec.md) (v0) y la
  [`constitución`](../constitucion.md).
- **Origen:** prompt P-03 (ver `bitacora/PROMPTS.md`).

## 1. Qué cambia respecto de v0

| Área | v0 | v1 |
|---|---|---|
| Usuarios | uno, sin registro | varios, con cuenta (Google de preferencia) |
| Base de datos | SQLite en claro | PostgreSQL con RLS y campos sensibles cifrados (esquema de EMA) |
| Datos de mercado | precios simulados o CSV | pantalla "Mercados" con datos de la bolsa chilena y la de EE. UU. |
| Ingreso de gastos | chat o cartola CSV | además, foto o escaneo de boletas |
| Modelos | cliente Ollama directo | detrás de puertos (`LLMPort`, `VisionPort`); locales por defecto |

## 2. ¿Conexión directa con las cuentas bancarias?

**Sí existe, pero no es viable para esta versión.** Hay dos caminos:

1. **Agregadores con consentimiento del usuario** (p. ej. Fintoc, Floid, Tupana, Clay): el usuario conecta
   su banco en un *widget* del proveedor y la app recibe sus movimientos por API o *webhook*, casi en
   tiempo real. Requiere contrato comercial y llaves del proveedor (los *sandbox* suelen pedir empresa) y
   manejar referencias de conexión como dato sensible. EMA ya modela esto con una lista
   `BANCO_PROVEEDORES` y un proveedor simulado (`tupana_simulado`) para probar sin banco real.
2. **Sistema de Finanzas Abiertas (Ley Fintec 21.521)**: la CMF reguló las API estándar en la NCG 514 y,
   en junio de 2026, publicó la NCG 569 con el anexo técnico. La entrada en operación está anunciada para
   julio de 2027 (un documento de la CMF muestra julio de 2028; hay que confirmarlo) y hay un *sandbox*
   tecnológico previsto para octubre de 2026. Las app de terceros deberán registrarse como proveedores.

**Decisión v1:** implementar el **escaneo de boletas** (RF-35…RF-39) y dejar diseñado un `BancoPort`
con un proveedor simulado, como en EMA, para conectar un agregador real cuando exista contrato o cuando
opere el Sistema de Finanzas Abiertas.

## 3. Requisitos funcionales (continúan la numeración de 001)

### Cuentas de usuario
- **RF-29** El usuario debe poder registrarse e iniciar sesión **con Google** (OpenID Connect, flujo
  *authorization code* con PKCE, `state` y `nonce`; se validan `iss`, `aud` y `exp` del `id_token`).
- **RF-30** Debe existir registro con correo y contraseña como alternativa (contraseña con `scrypt` o
  `argon2id`; nunca en claro ni cifrada de forma reversible).
- **RF-31** La sesión es una cookie `HttpOnly`, `SameSite=Lax`, con un token aleatorio cuyo HMAC se guarda
  en la base; caduca y se puede cerrar. Las peticiones que modifican datos verifican `Origin`.
- **RF-32** Cada usuario ve **solo sus datos** (movimientos, operaciones, boletas, auditoría y sesiones de chat).

### Pantalla de mercados
- **RF-33** Una pantalla "Mercados" muestra acciones de la **Bolsa de Santiago** y de **EE. UU.**
  (NYSE/Nasdaq): último precio, variación del día, gráfico histórico y botón "registrar compra".
- **RF-34** Los datos se obtienen por *scraping* o API pública mediante un `MercadoPort` con un adaptador
  por fuente, con caché (≥ 15 min), límite de frecuencia, `User-Agent` identificable, respeto de
  `robots.txt` y de los términos de uso. Se muestra la fuente, la hora del dato y el aviso de que no es
  una recomendación de inversión (P7). Si la fuente falla, se muestra el último dato guardado con su fecha.

### Boletas
- **RF-35** El usuario puede **subir o fotografiar** una boleta (`<input accept="image/*" capture>`).
- **RF-36** Un `VisionPort` extrae comercio, fecha, total, ítems y categoría sugerida como JSON validado
  contra un esquema. Por defecto con un **modelo local de visión** (Ollama, `gemma3:4b`, que es multimodal).
- **RF-37** Antes de guardar, el usuario **confirma o corrige** los datos; recién entonces se registra el gasto.
- **RF-38** El texto extraído pasa por el enmascarado y el detector de inyección (una boleta es contenido
  de terceros, nunca instrucciones).
- **RF-39** La imagen **no se guarda** después de procesarla (salvo que el usuario lo pida; en ese caso se
  cifra como archivo, ver plan §3).

### Proveedores de modelos
- **RF-40** El LLM y la visión se usan solo a través de `LLMPort` y `VisionPort`. Proveedor por variable de
  entorno (`LLM_PROVEEDOR`, `VISION_PROVEEDOR`); **valor por defecto y único implementado: `ollama` local**.
- **RF-41** Los adaptadores de API externas **no se implementan** hasta que el equipo lo indique de forma
  explícita. Cuando se agreguen, el texto que viaje debe ir enmascarado igual que hoy.

### Base de datos cifrada (como en EMA)
- **RF-42** PostgreSQL con **Row Level Security**: toda tabla de usuario tiene `usuario_id`, `ENABLE` y
  `FORCE ROW LEVEL SECURITY` y la policy `aislamiento_usuario`; la app se conecta con un rol sin privilegios
  de dueño y fija `SET LOCAL app.usuario_id` en cada transacción (doble barrera: filtro en la consulta +
  RLS).
- **RF-43** Los campos sensibles se guardan en columnas `*_cifrado` con **AES-256-GCM**, cifrado de sobre
  y la misma estructura que EMA (plan §3). Hay un catálogo de campos cifrados y una prueba que lo compara
  con `information_schema`.
- **RF-44** Búsquedas por dato sensible (correo para iniciar sesión, RUT) usan **índices ciegos**
  `HMAC-SHA256` en columnas `*_hmac`, nunca el valor en claro.
- **RF-45** Los datos sensibles que hoy el enmascarado descarta (RUT, cuentas, correos, teléfonos) se
  guardan **cifrados** en una bóveda del usuario, vinculados al marcador que ve el LLM. **Nunca** se guardan
  claves, PIN, CVV ni el número completo de una tarjeta (solo sus últimos 4 dígitos).
- **RF-46** La auditoría guarda su detalle cifrado.

## 4. Requisitos no funcionales

- **RNF-08** Todo sigue corriendo en el computador del usuario (Docker Compose: PostgreSQL y Ollama). Los
  únicos servicios externos son Google (identidad) y las fuentes de datos de mercado (solo se envían
  nemotécnicos, nunca datos del usuario).
- **RNF-09** Las pruebas de cifrado usan vectores fijos (llave y nonce inyectados), como en EMA.
- **RNF-10** Las 84 conversaciones de 001 siguen pasando por usuario, sin cambios en las métricas.

## 5. Criterios de aceptación

| ID | Criterio |
|---|---|
| CA-09 | Con un cliente OAuth de Google configurado, "Continuar con Google" crea la cuenta y abre la app. |
| CA-10 | El usuario A no ve ningún dato de B, aunque la consulta omita el filtro por usuario (prueba de RLS). |
| CA-11 | En la base no aparece en claro ningún RUT, correo, descripción ni texto de boleta (volcado de la base). |
| CA-12 | Cambiar el tenant, la tabla, la columna o un byte de un sobre hace fallar el descifrado. |
| CA-13 | Una foto de boleta produce un gasto propuesto; al confirmarlo queda registrado y la imagen no queda guardada. |
| CA-14 | La pantalla Mercados muestra al menos SQM-B y AAPL con su fuente y hora; sin red muestra el último dato guardado. |

## 6. Preguntas abiertas

1. **Cliente OAuth de Google:** lo crea el equipo en Google Cloud Console (tipo "Aplicación web", URI de
   redirección `http://127.0.0.1:8000/auth/google/callback`). Sin él solo funciona el registro con correo.
2. **Fuente de datos de mercado:** ver plan §2; hay que revisar los términos de uso antes de elegir.
3. **Custodia de la KEK:** OpenBao Transit como en EMA, o un archivo local con permisos 0600 para la demo.
