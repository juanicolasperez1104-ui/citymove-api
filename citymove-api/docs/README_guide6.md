# CityMove API – Guide 6 (hexagonal architecture + Colombian open data)

Citizen reports of urban-infrastructure issues (SDG 11). FastAPI · Python 3.12.

## Layout
```
app/
  domain/          entities, value objects, ports (pure Python)
    reports/  territory/  opendata/  shared/
  application/     use cases with constructor injection
    report_service.py  open_data_service.py  ports.py
  infrastructure/  adapters
    persistence/   SQLAlchemy repository
    opendata/      DANE DIVIPOLA + datos.gov.co catalog adapters
    resilience/    circuit breaker, retry with backoff, resilient HTTP client
    analytics/     DuckDB queries
  api/             FastAPI routers, schemas, error mapping, container (composition root)
tests/             domain / application (mocks) / infrastructure / api
docs/adr/          ADR 0001 (English)
scripts/           fetch_open_data.py, demo_circuit_breaker.py
```

## Run
```bash
pip install -r requirements.txt
pytest -v --cov=app                       # 60 tests, no network needed
uvicorn app.main:create_app --factory --reload
# http://127.0.0.1:8000/docs       Swagger
# POST /api/v1/open-data/refresh    download DIVIPOLA into DuckDB
# http://127.0.0.1:8000/dashboard  chart + statistics + breaker states
python scripts/fetch_open_data.py         # live data + DuckDB results + cross-check
python scripts/demo_circuit_breaker.py --break   # watch CLOSED -> OPEN -> HALF_OPEN
```
Optional: `DATOS_GOV_APP_TOKEN` (Socrata app token) and `DATABASE_URL`.

## Merging into the Guide 5 repository
This code was rebuilt from the Guide 5 report, not from the original repository.
Keep the Guide 5 AI files and move them like this:

| Guide 5 file | New place |
|---|---|
| app/models.py (ORM Report) | infrastructure/persistence/orm.py (already rewritten) |
| app/schemas.py | api/schemas.py (merge field names with yours) |
| app/routers/reports.py | api/routers/reports.py (already rewritten) |
| app/llm.py | infrastructure/llm/gemini_client.py implementing a new domain/triage `LLMPort` |
| app/prompts.py, app/rag.py | infrastructure/llm/ (adapters used by an application TriageService) |
| app/routers/ai.py | api/routers/ai.py calling TriageService from the container |
| tests/test_ai.py, test_llm_client.py | tests/api and tests/infrastructure |
