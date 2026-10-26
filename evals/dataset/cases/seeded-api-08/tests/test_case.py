from datetime import date

from fleet.api import (
    fleet_summary,
    list_vehicles,
    record_service,
    register_vehicle,
    retire_vehicle,
    transfer_vehicle,
    vehicle_detail,
)
from fleet.maintenance import Reading, ingest_readings, service_report
from fleet.registry import VehicleRegistry


def _registry() -> VehicleRegistry:
    registry = VehicleRegistry()
    for plate, depot, km in [("AB-123-CD", "north", 14_500), ("EF 456 GH", "south", 2_000), ("JK789LM", "north", 30_100)]:
        status, _ = register_vehicle(
            registry, {"plate": plate, "make": "Ford", "model": "Transit", "depot": depot, "odometer_km": km}
        )
        assert status == 201
    return registry


def test_ingest_reports_unknown_plates_and_applies_the_rest():
    registry = _registry()
    readings = [
        Reading("AB123CD", 15_200),
        Reading("NEW-001", 40),
        Reading("EF456GH", 1_900),
        Reading("JK789LM", 30_400),
    ]
    report = ingest_readings(registry, readings)
    assert report.unknown == ["NEW-001"]
    assert report.rejected == ["EF456GH"]
    assert report.recorded == 2
    assert report.became_due == ["AB123CD"]
    assert vehicle_detail(registry, "jk789lm")[1]["odometer_km"] == 30_400


def test_detail_and_retirement_endpoints():
    registry = _registry()
    assert vehicle_detail(registry, "ZZ999")[0] == 404
    assert vehicle_detail(registry, "not a plate!")[0] == 404
    assert retire_vehicle(registry, "ZZ999", {"on": "2026-09-01", "reason": "sold"})[0] == 404
    assert retire_vehicle(registry, "JK789LM", {"on": "2026-09-01", "reason": "lost"})[0] == 400
    status, body = retire_vehicle(registry, "JK789LM", {"on": "2026-09-01", "reason": "sold"})
    assert status == 200
    assert body["active"] is False and body["retired_on"] == "2026-09-01" and body["service_due"] is False
    assert retire_vehicle(registry, "JK789LM", {"on": "2026-09-02", "reason": "sold"})[0] == 409
    assert transfer_vehicle(registry, "JK789LM", {"depot": "south"})[0] == 409
    assert [v["plate"] for v in list_vehicles(registry, {"depot": "north"})[1]["items"]] == ["AB123CD"]
    everything = list_vehicles(registry, {"include_retired": "true"})[1]
    assert everything["count"] == 3


def test_service_report_skips_retired_vehicles():
    registry = _registry()
    registry.record_service("AB123CD", date(2026, 3, 1))
    assert [row["plate"] for row in service_report(registry)] == ["JK789LM"]
    registry.retire("JK789LM", date(2026, 9, 1), "scrapped")
    assert service_report(registry) == []
    status, body = transfer_vehicle(registry, "AB123CD", {"depot": "south"})
    assert status == 200 and body["depot"] == "south"


def test_service_endpoint_and_summary():
    registry = _registry()
    assert record_service(registry, "ZZ999", {"on": "2026-05-01"})[0] == 404
    assert record_service(registry, "JK789LM", {"on": "May 1st"})[0] == 400
    status, body = record_service(registry, "JK789LM", {"on": "2026-05-01"})
    assert status == 200 and body["service_due"] is False
    registry.retire("EF456GH", date(2026, 6, 1), "lease_returned")
    assert record_service(registry, "EF456GH", {"on": "2026-06-02"})[0] == 409
    assert fleet_summary(registry)[1] == {
        "depots": {
            "north": {"active": 2, "retired": 0, "service_due": 0},
            "south": {"active": 0, "retired": 1, "service_due": 0},
        },
        "totals": {"active": 2, "retired": 1, "service_due": 0},
    }
