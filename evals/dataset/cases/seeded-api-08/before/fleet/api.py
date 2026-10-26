"""Handlers behind the fleet admin API. Each returns (status code, JSON-serialisable body)."""

from __future__ import annotations

from typing import Any

from fleet.models import Vehicle
from fleet.registry import DuplicateVehicle, VehicleRegistry

Response = tuple[int, dict[str, Any]]


def serialise(vehicle: Vehicle) -> dict[str, Any]:
    return {
        "plate": vehicle.plate,
        "make": vehicle.make,
        "model": vehicle.model,
        "depot": vehicle.depot,
        "odometer_km": vehicle.odometer_km,
        "service_due": vehicle.service_due(),
    }


def register_vehicle(registry: VehicleRegistry, body: dict[str, Any]) -> Response:
    try:
        vehicle = Vehicle(
            plate=str(body["plate"]),
            make=str(body["make"]),
            model=str(body["model"]),
            depot=str(body["depot"]),
            odometer_km=int(body.get("odometer_km", 0)),
        )
        registry.add(vehicle)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, DuplicateVehicle):
            return 409, {"error": f"{exc} is already registered"}
        return 400, {"error": f"invalid vehicle: {exc}"}
    return 201, serialise(vehicle)


def vehicle_detail(registry: VehicleRegistry, plate: str) -> Response:
    try:
        vehicle = registry.get(plate)
    except (KeyError, ValueError):
        return 404, {"error": f"no vehicle {plate}"}
    return 200, serialise(vehicle)


def list_vehicles(registry: VehicleRegistry, query: dict[str, str]) -> Response:
    depot = query.get("depot") or None
    items = [serialise(vehicle) for vehicle in registry.vehicles(depot)]
    return 200, {"items": items, "count": len(items)}
