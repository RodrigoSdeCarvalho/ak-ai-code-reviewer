"""Vehicle records kept by the fleet registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SERVICE_INTERVAL_KM = 15_000


@dataclass
class Vehicle:
    plate: str
    make: str
    model: str
    depot: str
    odometer_km: int = 0
    last_service_km: int = 0
    last_service_on: date | None = None
    notes: list[str] = field(default_factory=list)

    def km_since_service(self) -> int:
        return self.odometer_km - self.last_service_km

    def service_due(self, interval_km: int = SERVICE_INTERVAL_KM) -> bool:
        return self.km_since_service() >= interval_km


def normalise_plate(plate: str) -> str:
    """Return the canonical form of a number plate: upper case, no spaces or dashes."""
    cleaned = plate.replace(" ", "").replace("-", "").upper()
    if not cleaned.isalnum() or not 2 <= len(cleaned) <= 10:
        raise ValueError(f"invalid number plate {plate!r}")
    return cleaned
