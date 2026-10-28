# ADR 0001 – Hexagonal architecture, bounded contexts and resilient open-data integration

- **Status:** Accepted
- **Date:** 2026-10-27
- **Author:** Juan Nicolás Pérez Alfaro (Taller de Programación, UMB, Lab Guide 6)

## Context

CityMove lets citizens report urban-infrastructure problems (potholes, broken
streetlights, damaged sidewalks). After Lab Guide 5 the backend was a layered
FastAPI application: routers, Pydantic schemas, SQLAlchemy models and AI modules
(Gemini client, prompts, TF-IDF RAG). Business rules lived inside the routers and
the ORM model, so the only way to test a rule was through HTTP and a database.

Lab Guide 6 adds two new needs:

1. Use official Colombian open data. A report should carry a DANE DIVIPOLA
   municipality code that is checked against the official list.
2. Analyse that data together with the reports (DuckDB) and show it in the UI.

External open-data services can be slow or unavailable. A citizen report must
never be lost because a government portal is down.

## Problem

How do we organise the code so that business rules are testable without HTTP,
databases or the internet, and so that unreliable external APIs cannot break
the core use case (creating a report)?

## Options considered

| Option | Pros | Cons |
|---|---|---|
| A. Keep the layered structure and call datos.gov.co from the routers | Least work | Rules stay coupled to FastAPI/SQLAlchemy; HTTP calls inside endpoints are hard to test; no single place for resilience |
| B. Hexagonal architecture (ports and adapters) with four packages: `domain`, `application`, `api`, `infrastructure` | Domain is pure Python; every external system sits behind a port; adapters can be swapped by fakes in tests | More files and mapping code (ORM row ↔ domain object, schema ↔ domain object) |
| C. Split into microservices per context | Independent deployment | Far beyond the needs and team size (one student); network calls between contexts add new failure modes |

## Decision

We adopt **option B**.

- `app/domain` – entities, value objects, domain errors and **ports** (abstract
  classes). No imports of FastAPI, Pydantic, SQLAlchemy, httpx or DuckDB.
  This rule is enforced by an automated test (`tests/domain/test_architecture.py`).
- `app/application` – use cases (`ReportService`, `OpenDataService`). They
  receive every dependency **through the constructor**.
- `app/infrastructure` – driven adapters: SQLAlchemy repository, DIVIPOLA and
  catalog adapters for datos.gov.co, DuckDB analytics, resilience utilities.
- `app/api` – driving adapter: FastAPI routers, Pydantic schemas, error mapping
  and the **composition root** (`container.py`), the only module that knows
  the concrete classes.

### Bounded contexts

| Context | Responsibility | Main elements |
|---|---|---|
| **Reports** (core) | Life cycle of a citizen report: creation, validation, status transitions | `Report`, `Status`, `ReportRepository`, `ReportService` |
| **Territory** (supporting) | Official political-administrative division of Colombia | `Municipality`, `TerritorialDataPort`, `DaneDivipolaAdapter` |
| **Open data & analytics** (supporting) | Provenance of public datasets and analytical queries | `DatasetCatalogPort`, `AnalyticsPort`, `OpenDataService`, `DuckDBAnalytics` |
| **Triage / AI** (supporting, from Guide 5) | LLM classification and RAG | To be moved behind an `LLMPort` (see Consequences) |

Reports and Territory talk through a port, not through shared tables: Reports
only stores the 5-digit code and a `municipality_verified` flag. DIVIPOLA terms
(`cod_mpio`, `nom_mpio`, decimal-comma coordinates) are translated inside the
adapter, which acts as an **anti-corruption layer**.

### External integrations

| Integration | Endpoint (verified 2026-10-27) | Use in CityMove |
|---|---|---|
| DANE DIVIPOLA on datos.gov.co (Socrata SODA) | `https://www.datos.gov.co/resource/gdxc-w37w.json` | Validate municipality codes; DuckDB analytics |
| datos.gov.co dataset metadata API | `https://www.datos.gov.co/api/views/{id}` | Provenance shown to users: publisher, licence, last update |

Every call goes through `ResilientJsonClient`:

- **Timeout:** 10 s read, 5 s connect.
- **Retry with exponential backoff and full jitter:** 3 attempts, ceilings
  0.5 s → 1 s (max 8 s); `Retry-After` is honoured but capped. Only timeouts,
  connection errors, 429 and 5xx are retried. 4xx responses and malformed bodies
  are not retried.
- **Circuit breaker per integration** (CLOSED → OPEN after 3 failed logical
  calls → HALF_OPEN after 30 s → CLOSED on one success / OPEN on one failure).
  The breaker wraps the whole retry sequence, so an open circuit fails in
  ~0 ms without retries. A 404 does not count as a failure.
- **Graceful degradation:** if DIVIPOLA is unavailable, the report is saved with
  `municipality_verified=false`; the DIVIPOLA list is cached for 24 h and a
  stale copy is served if the source fails (the dataset is updated twice a year).

## Consequences

**Positive**

- Use cases are unit-tested with `unittest.mock.create_autospec` (the Python
  counterpart of Mockito), with no database or network.
- CI does not depend on datos.gov.co being online; the real endpoints are
  exercised by `scripts/fetch_open_data.py` and `scripts/demo_circuit_breaker.py`.
- Replacing SQLite by PostgreSQL, or DIVIPOLA by a local file, means writing one
  adapter and changing the composition root.

**Negative / risks**

- More code: mapping functions and duplicated shapes (domain object, ORM row,
  Pydantic schema).
- Both integrations run on the same platform (datos.gov.co). An outage of the
  portal affects both; separate breakers only isolate the symptoms.
- The circuit breaker state lives in memory, per process. With several
  workers each one has its own breaker. Acceptable for the current deployment.
- The Guide 5 AI modules have not been migrated yet. Plan: `LLMPort` in
  `domain/triage`, Gemini client and RAG retriever as infrastructure adapters,
  `TriageService` in application.

## References

- Cockburn, A. (2005). *Hexagonal architecture*. https://alistair.cockburn.us/hexagonal-architecture/
- Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of software*. Addison-Wesley.
- Nygard, M. (2011). *Documenting architecture decisions*. https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- Fowler, M. (2014). *CircuitBreaker*. https://martinfowler.com/bliki/CircuitBreaker.html
- Brooker, M. (2015). *Exponential backoff and jitter*. AWS Architecture Blog. https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
