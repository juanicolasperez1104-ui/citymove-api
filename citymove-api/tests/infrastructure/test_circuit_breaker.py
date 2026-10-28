import pytest

from app.infrastructure.resilience.circuit_breaker import (CircuitBreaker, CircuitOpenError,
                                                           CircuitState)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def boom():
    raise ConnectionError("down")


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cb(clock):
    return CircuitBreaker("test", failure_threshold=3, recovery_timeout=30, clock=clock)


def fail(cb, times):
    for _ in range(times):
        with pytest.raises(ConnectionError):
            cb.call(boom)


def test_closed_to_open_after_threshold(cb):
    fail(cb, 2)
    assert cb.state is CircuitState.CLOSED
    fail(cb, 1)
    assert cb.state is CircuitState.OPEN


def test_open_fails_fast_without_calling_the_dependency(cb):
    fail(cb, 3)
    calls = []
    with pytest.raises(CircuitOpenError) as exc:
        cb.call(lambda: calls.append(1))
    assert calls == [] and exc.value.retry_after == pytest.approx(30)


def test_open_to_half_open_to_closed(cb, clock):
    fail(cb, 3)
    clock.t = 30.0
    assert cb.state is CircuitState.HALF_OPEN
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state is CircuitState.CLOSED
    assert cb.transitions == [("closed", "open"), ("open", "half_open"), ("half_open", "closed")]


def test_failure_in_half_open_reopens(cb, clock):
    fail(cb, 3)
    clock.t = 31.0
    fail(cb, 1)
    assert cb.state is CircuitState.OPEN
    clock.t = 40.0                     # timer restarted at t=31
    assert cb.state is CircuitState.OPEN


def test_half_open_allows_a_single_trial_call(cb, clock):
    fail(cb, 3)
    clock.t = 30.0

    def trial():
        with pytest.raises(CircuitOpenError):   # second concurrent trial is rejected
            cb.call(lambda: "x")
        return "ok"

    assert cb.call(trial) == "ok"


def test_success_resets_the_failure_counter(cb):
    fail(cb, 2)
    cb.call(lambda: None)
    fail(cb, 2)
    assert cb.state is CircuitState.CLOSED


def test_errors_marked_as_neutral_do_not_open_the_circuit(clock):
    cb = CircuitBreaker("t", failure_threshold=1, clock=clock,
                        counts_as_failure=lambda e: not isinstance(e, KeyError))
    with pytest.raises(KeyError):
        cb.call(lambda: {}["missing"])
    assert cb.state is CircuitState.CLOSED
