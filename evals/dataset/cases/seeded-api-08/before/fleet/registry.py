"""In-memory registry of the vehicles the company operates."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from fleet.models import Vehicle, normalise_plate


class DuplicateVehicle(ValueError):
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
        """Return the vehicle registered under `plate`; raise KeyError if there is none."""
        return self._vehicles[normalise_plate(plate)]

    def vehicles(self, depot: str | None = None) -> Iterator[Vehicle]:
        for plate in sorted(self._vehicles):
            vehicle = self._vehicles[plate]
            if depot is None or vehicle.depot == depot:
                yield vehicle

    def record_odometer(self, plate: str, km: int) -> Vehicle:
        vehicle = self.get(plate)
        if km < vehicle.odometer_km:
            raise ValueError(f"{vehicle.plate}: odometer cannot go back from {vehicle.odometer_km} to {km}")
        vehicle.odometer_km = km
        return vehicle

    def record_service(self, plate: str, on: date) -> Vehicle:
        vehicle = self.get(plate)
        vehicle.last_service_km = vehicle.odometer_km
        vehicle.last_service_on = on
        return vehicle
