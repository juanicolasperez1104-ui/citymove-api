"""Shows the circuit breaker states against the REAL DIVIPOLA endpoint.

  python scripts/demo_circuit_breaker.py            # normal network: stays CLOSED
  python scripts/demo_circuit_breaker.py --break    # points to an unreachable host
                                                    # to watch CLOSED -> OPEN -> HALF_OPEN
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.shared.errors import ExternalDataUnavailable  # noqa: E402
from app.infrastructure.opendata.divipola_adapter import DIVIPOLA_URL, DaneDivipolaAdapter  # noqa: E402
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker  # noqa: E402
from app.infrastructure.resilience.http_client import ResilientJsonClient, breaker_failure_rule  # noqa: E402
from app.infrastructure.resilience.retry import RetryPolicy  # noqa: E402

url = "https://unreachable.invalid/resource/gdxc-w37w.json" if "--break" in sys.argv else DIVIPOLA_URL
breaker = CircuitBreaker("dane-divipola", failure_threshold=3, recovery_timeout=5,
                         counts_as_failure=breaker_failure_rule)
retry = RetryPolicy(max_attempts=3, base_delay=0.2, max_delay=1.0)
adapter = DaneDivipolaAdapter(ResilientJsonClient("DANE DIVIPOLA", httpx.Client(timeout=5.0),
                                                  breaker, retry), url=url)
print(f"Endpoint: {url}")
for i in range(1, 6):
    if i == 5:
        print("... waiting 5.5 s (recovery_timeout) ...")
        time.sleep(5.5)
        print(f"state before call {i}: {breaker.state.value.upper()}")
    start = time.perf_counter()
    try:
        m = adapter.get_municipality("11001")
        outcome = f"OK -> {m.name if m else 'not found'}"
    except ExternalDataUnavailable as exc:
        outcome = f"FAIL -> {exc.reason}"
    took = time.perf_counter() - start
    print(f"call {i}: {outcome:<45} {took:5.2f}s  state={breaker.state.value.upper()} "
          f"failures={breaker.failure_count}")
print("transitions:", breaker.transitions)
print("backoff delays waited (s):", [round(d, 2) for d in retry.delays])
