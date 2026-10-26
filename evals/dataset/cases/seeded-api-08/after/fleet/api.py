"""Handlers behind the fleet admin API. Each returns (status code, JSON-serialisable body)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fleet.models import Vehicle
from fleet.registry import DuplicateVehicle, VehicleRegistry, VehicleRetired

Response = tuple[int, dict[str, Any]]


def serialise(vehicle: Vehicle) -> dict[str, Any]:
    return {
        "plate": vehicle.plate,
        "make": vehicle.make,
        "model": vehicle.model,
        "depot": vehicle.depot,
        "odometer_km": vehicle.odometer_km,
        "service_due": vehicle.service_due(),
        "active": vehicle.active,
        "retired_on": vehicle.retired_on.isoformat() if vehicle.retired_on else None,
        "retirement_reason": vehicle.retirement_reason,
    }


def _not_found(plate: str) -> Response:
    return 404, {"error": f"no vehicle {plate}"}


def _lookup(registry: VehicleRegistry, plate: str) -> Vehicle | None:
    try:
        return registry.get(plate)
    except ValueError:
        return None


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
    vehicle = _lookup(registry, plate)
    if vehicle is None:
        return _not_found(plate)
    return 200, serialise(vehicle)


def list_vehicles(registry: VehicleRegistry, query: dict[str, str]) -> Response:
    depot = query.get("depot") or None
    include_retired = query.get("include_retired", "").lower() in ("1", "true", "yes")
    items = [serialise(vehicle) for vehicle in registry.vehicles(depot, include_retired=include_retired)]
    return 200, {"items": items, "count": len(items)}


def transfer_vehicle(registry: VehicleRegistry, plate: str, body: dict[str, Any]) -> Response:
    if _lookup(registry, plate) is None:
        return _not_found(plate)
    depot = str(body.get("depot", "")).strip()
    if not depot:
        return 400, {"error": "depot is required"}
    try:
        vehicle = registry.transfer(plate, depot)
    except VehicleRetired:
        return 409, {"error": f"{plate} is retired"}
    return 200, serialise(vehicle)


def retire_vehicle(registry: VehicleRegistry, plate: str, body: dict[str, Any]) -> Response:
    if _lookup(registry, plate) is None:
        return _not_found(plate)
    try:
        on = date.fromisoformat(str(body["on"]))
        vehicle = registry.retire(plate, on, str(body.get("reason", "")))
    except VehicleRetired:
        return 409, {"error": f"{plate} is already retired"}
    except (KeyError, ValueError) as exc:
        return 400, {"error": f"invalid retirement: {exc}"}
    return 200, serialise(vehicle)


def record_service(registry: VehicleRegistry, plate: str, body: dict[str, Any]) -> Response:
    if _lookup(registry, plate) is None:
        return _not_found(plate)
    try:
        on = date.fromisoformat(str(body["on"]))
    except (KeyError, ValueError) as exc:
        return 400, {"error": f"invalid service date: {exc}"}
    try:
        vehicle = registry.record_service(plate, on)
    except VehicleRetired:
        return 409, {"error": f"{plate} is retired"}
    return 200, serialise(vehicle)


def fleet_summary(registry: VehicleRegistry) -> Response:
    depots: dict[str, dict[str, int]] = {}
    for vehicle in registry.vehicles(include_retired=True):
        counts = depots.setdefault(vehicle.depot, {"active": 0, "retired": 0, "service_due": 0})
        if vehicle.active:
            counts["active"] += 1
            counts["service_due"] += vehicle.service_due()
        else:
            counts["retired"] += 1
    totals = {key: sum(counts[key] for counts in depots.values()) for key in ("active", "retired", "service_due")}
    return 200, {"depots": dict(sorted(depots.items())), "totals": totals}
