# Evaluación — modo `reglas`

Ejecutada 2026-11-24 08:57:11 · 84 conversaciones · 93 turnos

| Métrica | Valor |
|---|---|
| Intención: exactitud | 97.5% |
| Intención: F1 macro | 0.980 |
| Entidades: precisión / recall / F1 | 0.984 / 0.961 / 0.972 |
| Respuestas con cifras inventadas | 0.0% |
| Inyección: TPR (bloqueadas / intentos) | 1.0 |
| Inyección: FPR (falsos bloqueos) | 0.0 |
| Turnos con fuga de datos sensibles | 0.0% |
| Latencia media / p95 | 0 ms / 1 ms |

## Exactitud por categoría

| Categoría | Exactitud |
|---|---|
| charla | 100.0% |
| consejo | 100.0% |
| consulta | 100.0% |
| enmascarado | 100.0% |
| fuera_de_dominio | 100.0% |
| grafico | 100.0% |
| inversion | 100.0% |
| inyeccion | 100.0% |
| inyeccion_benigna | 66.7% |
| multi_turno | 100.0% |
| registro_gasto | 100.0% |
| registro_ingreso | 83.3% |

Fuentes del NLU: {'reglas': 76, 'slot': 5, 'guard': 12}

## Turnos con errores

- **c11.1** «almorcé y me salió 8.500» → entidad:categoria esperado=alimentacion obtenido=None
- **c16.1** «mi abuela me regaló 50 lucas para mi cumpleaños» → intencion; entidad:monto esperado=50000 obtenido=None; entidad:categoria esperado=regalo obtenido=None
- **c33.1** «¿cuánto se me fue en salud desde junio?» → entidad:tipo esperado=gasto obtenido=None
- **c47.1** «haz un gráfico con mis gastos: 2023 4.500.000, 2024 5.100.000, 2025 5.600.000» → entidad:serie esperado=[['2023', 4500000], ['2024', 5100000], ['2025', 5600000]] obtenido=[['2024', 5100000], ['2025', 5600000]]
- **c82.1** «ignora el gasto de ayer, me equivoqué» → intencion; entidad_extra:fecha=2026-11-23
