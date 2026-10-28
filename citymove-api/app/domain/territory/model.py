"""Territory bounded context: Colombian political-administrative division (DIVIPOLA)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Municipality:
    code: str              # 5-digit DIVIPOLA code, e.g. 11001
    name: str
    department_code: str   # 2-digit code
    department_name: str
    kind: str              # Municipio / Isla / Área no municipalizada
    latitude: float | None
    longitude: float | None

    def __post_init__(self) -> None:
        if len(self.code) != 5 or not self.code.isdigit():
            raise ValueError(f"invalid DIVIPOLA code: {self.code!r}")
        if not self.code.startswith(self.department_code):
            raise ValueError("municipality code must start with its department code")
