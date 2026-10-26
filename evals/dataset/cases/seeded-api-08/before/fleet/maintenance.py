"""Nightly odometer ingestion from the telematics export, and the service-due report."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from fleet.models import SERVICE_INTERVAL_KM
from fleet.registry import VehicleRegistry


@dataclass(frozen=True)
class Reading:
    plate: str
    km: int


@dataclass
class IngestReport:
    recorded: int = 0
    unknown: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    became_due: list[str] = field(default_factory=list)


def ingest_readings(
    registry: VehicleRegistry, readings: Iterable[Reading], interval_km: int = SERVICE_INTERVAL_KM
) -> IngestReport:
    """Apply a batch of odometer readings.

    Readings for plates the registry does not know are reported, not applied: the telematics box is
    often fitted before the vehicle is registered. Readings lower than the current odometer are
    rejected.
    """
    report = IngestReport()
    for reading in readings:
        try:
            vehicle = registry.get(reading.plate)
        except KeyError:
            report.unknown.append(reading.plate)
            continue
        if reading.km < vehicle.odometer_km:
            report.rejected.append(vehicle.plate)
            continue
        was_due = vehicle.service_due(interval_km)
        registry.record_odometer(vehicle.plate, reading.km)
        report.recorded += 1
        if vehicle.service_due(interval_km) and not was_due:
            report.became_due.append(vehicle.plate)
    return report


def service_report(registry: VehicleRegistry, interval_km: int = SERVICE_INTERVAL_KM) -> list[dict[str, object]]:
    """List the vehicles due for a service, most overdue first."""
    due = [vehicle for vehicle in registry.vehicles() if vehicle.service_due(interval_km)]
    due.sort(key=lambda vehicle: vehicle.km_since_service(), reverse=True)
    return [
        {
            "plate": vehicle.plate,
            "depot": vehicle.depot,
            "km_since_service": vehicle.km_since_service(),
            "last_service_on": vehicle.last_service_on.isoformat() if vehicle.last_service_on else None,
        }
        for vehicle in due
    ]
