from app.domain.shared.errors import DomainError


class InvalidReport(DomainError):
    def __init__(self, field: str, message: str):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


class ReportNotFound(DomainError):
    def __init__(self, report_id: int):
        super().__init__(f"Report {report_id} was not found")
        self.report_id = report_id


class InvalidStatusTransition(DomainError):
    def __init__(self, current: str, requested: str):
        super().__init__(f"Cannot move a report from '{current}' to '{requested}'")


class UnknownMunicipality(DomainError):
    def __init__(self, code: str):
        super().__init__(f"Municipality code {code} does not exist in DIVIPOLA")
        self.code = code
