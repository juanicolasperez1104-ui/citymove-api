import pytest

from app.infrastructure.resilience.retry import PermanentError, RetryPolicy, TransientError


def flaky(failures, exc=TransientError("503")):
    state = {"calls": 0}

    def fn():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc
        return "ok"
    return fn, state


def policy(**kw):
    slept = []
    p = RetryPolicy(sleep=slept.append, rand=lambda: 1.0, **kw)  # rand=1 -> upper bound
    return p, slept


def test_retries_transient_errors_with_exponential_backoff():
    p, slept = policy(max_attempts=4, base_delay=0.5)
    fn, state = flaky(3)
    assert p.run(fn) == "ok"
    assert state["calls"] == 4 and slept == [0.5, 1.0, 2.0]


def test_backoff_is_capped():
    p, _ = policy(base_delay=1, max_delay=4)
    assert [p.backoff(n) for n in range(1, 6)] == [1, 2, 4, 4, 4]


def test_full_jitter_stays_within_ceiling():
    p = RetryPolicy(rand=lambda: 0.25, base_delay=2)
    assert p.backoff(2) == pytest.approx(1.0)   # ceiling 4 * 0.25


def test_permanent_errors_are_not_retried():
    p, slept = policy()
    fn, state = flaky(1, PermanentError("404"))
    with pytest.raises(PermanentError):
        p.run(fn)
    assert state["calls"] == 1 and slept == []


def test_gives_up_after_max_attempts():
    p, slept = policy(max_attempts=3)
    fn, state = flaky(10)
    with pytest.raises(TransientError):
        p.run(fn)
    assert state["calls"] == 3 and len(slept) == 2


def test_retry_after_header_is_respected_but_capped():
    p, slept = policy(max_attempts=2, base_delay=0.5, max_delay=8)
    fn, _ = flaky(1, TransientError("429", retry_after=30))
    p.run(fn)
    assert slept == [8]
