"""Domain and application errors. No framework imports allowed in this package."""


class DomainError(Exception):
    """Base class for business-rule violations."""


class ExternalDataUnavailable(Exception):
    """An external data source could not answer (timeout, 5xx, circuit open).

    Defined next to the domain so the application layer can react to it
    without knowing which HTTP library or provider produced it.
    """

    def __init__(self, source: str, reason: str, retry_after: float | None = None):
        super().__init__(f"{source} unavailable: {reason}")
        self.source = source
        self.reason = reason
        self.retry_after = retry_after
