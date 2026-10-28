# Runtime evidence (development sandbox, 2026-10-27, America/Bogota)

The sandbox where this was run has NO internet access to datos.gov.co
(DNS resolution fails with httpx.ConnectError). That made it possible to observe
the real failure path. Live-data evidence must be produced on a machine with
internet: `python scripts/fetch_open_data.py`.

## 1. scripts/demo_circuit_breaker.py --break
```
call 1: FAIL -> network error: ConnectError   0.14s  state=CLOSED failures=1
call 2: FAIL -> network error: ConnectError   0.53s  state=CLOSED failures=2
call 3: FAIL -> network error: ConnectError   0.18s  state=OPEN   failures=3
call 4: FAIL -> circuit open                  0.00s  state=OPEN   failures=3
... waiting 5.5 s (recovery_timeout) ...
state before call 5: HALF_OPEN
call 5: FAIL -> network error: ConnectError   0.35s  state=OPEN   failures=4
transitions: [('closed','open'), ('open','half_open'), ('half_open','open')]
backoff delays waited (s): [0.11, 0.03, 0.15, 0.38, 0.11, 0.06, 0.09, 0.26]
```

## 2. API running with uvicorn (production container, real adapters)
POST /api/v1/reports x3 with municipality_code=11001 -> 201, 201, 201
(0.38 s, 1.04 s, 0.65 s: time spent in retries with backoff)

GET /api/v1/reports/3 -> "municipality_verified": false  (report kept, check deferred)

GET /api/v1/health/integrations ->
[{"name":"dane-divipola","state":"open","failures":3,"failure_threshold":3,"recovery_timeout_s":30,"retry_after_s":30.0},
 {"name":"datosgov-catalog","state":"closed","failures":0,"failure_threshold":3,"recovery_timeout_s":60,"retry_after_s":0}]

GET /api/v1/territory/municipalities/11001 -> HTTP/1.1 503, retry-after: 30
{"status":503,"error":"Service Unavailable","detail":"DANE DIVIPOLA (datos.gov.co) unavailable: circuit open",...}

## 3. Endpoints verified with web_fetch (2026-10-27)
- https://www.datos.gov.co/api/views/gdxc-w37w -> JSON metadata: owner DANE, licence CC BY-SA 4.0,
  columns cod_dpto, dpto, cod_mpio, nom_mpio, tipo_municipio, longitud, latitud (text, decimal comma),
  1,122 rows (Municipio 1,103; Área no municipalizada 18; Isla 1), "Frecuencia de Actualización: Semestral".
- https://www.datos.gov.co/resource/gdxc-w37w.json?$select=dpto -> JSON array; without $limit the
  list stopped at TOLIMA (incomplete), which is why the adapter always sends $limit=2000.
