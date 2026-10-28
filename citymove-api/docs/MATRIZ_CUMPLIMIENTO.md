# Matriz de cumplimiento – Guía 6 (CityMove)

| Criterio (peso) | Estado | Evidencia en el repo | Qué falta |
|---|---|---|---|
| Arquitectura Hexagonal, 4 capas, pruebas pasando (25 %) | Hecho | `app/domain`, `app/application`, `app/api`, `app/infrastructure`; `tests/domain/test_architecture.py` | Ver CI en verde en GitHub |
| DI por constructor en ≥2 servicios + testabilidad (15 %) | Hecho (Python: `unittest.mock`, equivalente a Mockito) | `ReportService`, `OpenDataService`; `tests/application/` | — |
| ADR en inglés (10 %) | Hecho | `docs/adr/0001-...md` | — |
| 2 APIs colombianas + circuit breaker 3 estados + retry con backoff (30 %) | Hecho en código; datos reales sin descargar | `app/infrastructure/opendata`, `app/infrastructure/resilience`; `docs/evidence/runtime_evidence.md` | Correr `scripts/fetch_open_data.py` y `scripts/demo_circuit_breaker.py` con internet |
| DuckDB ≥2 queries + estadísticas + visualización en UI (10 %) | Hecho con datos de prueba | `app/infrastructure/analytics/duckdb_analytics.py`; `/dashboard` | Resultados con datos reales y captura del panel |
| Preguntas orientadoras + APA 7 (5 %) | 3 de 4 | Informe Word | Pregunta 4 (Copilot) con experiencia real |
| Video en inglés (5 %) | Pendiente (lo haces tú) | — | Grabar, subir a YouTube, poner link en el Word |

Pruebas: 60/60 aprobadas, 95 % de cobertura (`docs/evidence/pytest_output.txt`).
