# Constitución del proyecto — Asistente financiero personal (Lang-Chi)

Principios no negociables que toda especificación, plan, tarea y línea de código debe respetar.
Se trabaja con **Spec-Driven Development (SDD)**: primero la especificación (`spec.md`), luego el
plan técnico (`plan.md`), luego las tareas (`tasks.md`) y recién entonces el código. Cada tarea y
cada prueba cita el requisito que cubre (p. ej. `RF-03`).

## P1. Solo modelos locales
El LLM corre en la máquina del usuario (Ollama, `qwen3:4b` por defecto, `gemma3:4b` alternativo).
Ningún dato del usuario sale del computador. No se usan APIs de LLM en la nube.

## P2. El LLM interpreta, el código calcula
El LLM solo se usa para entender el mensaje (intención + datos) y, opcionalmente, para redactar.
Todo número que se muestra al usuario (saldos, totales, valores de portafolio) lo calcula Python
sobre la base de datos. Una respuesta con cifras que no vienen de los datos es un **defecto**
("respuesta inventada") y debe detectarse y medirse.

## P3. Privacidad por defecto
Los datos sensibles (RUT, tarjetas, cuentas bancarias, correos, teléfonos, claves) se enmascaran
**en el borde**, antes de llegar al LLM, a la base de datos o a la bitácora. El valor original no se
persiste en ninguna parte.

## P4. La entrada del usuario es dato, nunca instrucción
Toda entrada (chat, CSV, descripciones) se trata como dato no confiable. Hay defensas en capas
contra *prompt injection*: detector de patrones, delimitadores, salida estructurada con
intenciones en lista blanca, canario en el prompt de sistema y verificación de la salida.

## P5. Medible
La calidad se mide con ≥ 50 conversaciones de prueba anotadas: intenciones detectadas, datos
extraídos, respuestas inventadas, inyecciones bloqueadas y fugas de datos sensibles.

## P6. Trazable
Todo lo hecho queda en `bitacora/BITACORA.md` y todos los prompts (del usuario al agente y del
sistema al LLM) en `bitacora/PROMPTS.md`. La primera versión generada por IA se conserva cruda,
sin modificaciones, en `versiones/v0_cruda/`.

## P7. Sin asesoría personalizada de inversión
El asistente registra, consulta y grafica. No recomienda comprar ni vender instrumentos
específicos; ante esas preguntas entrega información general y un descargo de responsabilidad.
