"""In-memory registry of the vehicles the company operates."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from fleet.models import RETIREMENT_REASONS, Vehicle, normalise_plate


class DuplicateVehicle(ValueError):
    pass


class VehicleRetired(ValueError):
    pass


class VehicleRegistry:
    def __init__(self) -> None:
        self._vehicles: dict[str, Vehicle] = {}

    def __len__(self) -> int:
        return len(self._vehicles)

    def add(self, vehicle: Vehicle) -> Vehicle:
        vehicle.plate = normalise_plate(vehicle.plate)
        if vehicle.plate in self._vehicles:
            raise DuplicateVehicle(vehicle.plate)
        self._vehicles[vehicle.plate] = vehicle
        return vehicle

    def get(self, plate: str) -> Vehicle:
        """Return the vehicle registered under `plate`, retired or not; raise KeyError if there is none."""
        return self._vehicles[normalise_plate(plate)]

    def find(self, plate: str) -> Vehicle | None:
        """Return the vehicle registered under `plate`, retired or not, or None if there is none."""
        return self._vehicles.get(normalise_plate(plate))

    def _require(self, plate: str) -> Vehicle:
        vehicle = self.find(plate)
        if vehicle is None:
            raise KeyError(plate)
        return vehicle

    def vehicles(self, depot: str | None = None, include_retired: bool = False) -> Iterator[Vehicle]:
        for plate in sorted(self._vehicles):
            vehicle = self._vehicles[plate]
            if not include_retired and not vehicle.active:
                continue
            if depot is None or vehicle.depot == depot:
                yield vehicle

    def record_odometer(self, plate: str, km: int) -> Vehicle:
        vehicle = self._require(plate)
        if km < vehicle.odometer_km:
            raise ValueError(f"{vehicle.plate}: odometer cannot go back from {vehicle.odometer_km} to {km}")
        vehicle.odometer_km = km
        return vehicle

    def record_service(self, plate: str, on: date) -> Vehicle:
        vehicle = self._require(plate)
        if not vehicle.active:
            raise VehicleRetired(vehicle.plate)
        vehicle.last_service_km = vehicle.odometer_km
        vehicle.last_service_on = on
        return vehicle

    def transfer(self, plate: str, depot: str) -> Vehicle:
        vehicle = self._require(plate)
        if not vehicle.active:
            raise VehicleRetired(vehicle.plate)
        if vehicle.depot != depot:
            vehicle.notes.append(f"transferred from {vehicle.depot} to {depot}")
            vehicle.depot = depot
        return vehicle

    def retire(self, plate: str, on: date, reason: str) -> Vehicle:
        """Take a vehicle out of service. Its record is kept for reporting and audits."""
        if reason not in RETIREMENT_REASONS:
            raise ValueError(f"unknown retirement reason {reason!r}")
        vehicle = self._require(plate)
        if not vehicle.active:
            raise VehicleRetired(vehicle.plate)
        if vehicle.last_service_on is not None and on < vehicle.last_service_on:
            raise ValueError(f"{vehicle.plate}: cannot retire before its last service on {vehicle.last_service_on}")
        vehicle.retired_on = on
        vehicle.retirement_reason = reason
        return vehicle
