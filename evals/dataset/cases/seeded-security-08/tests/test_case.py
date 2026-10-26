import pytest
from loyalty.api import LoyaltyApi, PointsLedger, Request, Reward
from loyalty.settings import Settings, SettingsError

ENV = {
    "LOYALTY_PROGRAM_NAME": "Bean Points",
    "LOYALTY_ALLOWED_ORIGINS": "https://app.beanpoints.example/",
    "LOYALTY_PARTNER_DOMAINS": "*.Kettle.Example, roastery.example",
    "LOYALTY_CORS_MAX_AGE": "300",
}


def _api() -> tuple[LoyaltyApi, PointsLedger]:
    ledger = PointsLedger([Reward("mug", "Enamel mug", 400), Reward("latte", "Free latte", 150)])
    ledger.credit(7, 500)
    return LoyaltyApi(Settings.from_mapping(ENV), ledger), ledger


def _balance(api: LoyaltyApi, origin: str) -> dict[str, str]:
    response = api.handle(Request("GET", "/v1/balance", {"origin": origin}, member_id=7))
    assert response.status == 200 and response.body == {"member": 7, "points": 500}
    return response.headers


def test_settings_normalise_partner_domains():
    settings = Settings.from_mapping(ENV)
    assert settings.partner_domains == ("kettle.example", "roastery.example")
    assert settings.allowed_origins == ("https://app.beanpoints.example",)
    with pytest.raises(SettingsError):
        Settings.from_mapping({"LOYALTY_PARTNER_DOMAINS": "https://kettle.example"})


def test_exact_and_partner_origins_get_credentialed_access():
    api, _ = _api()
    for origin in ("https://app.beanpoints.example", "https://shop.kettle.example", "https://kettle.example"):
        headers = _balance(api, origin)
        assert headers["Access-Control-Allow-Origin"] == origin
        assert headers["Access-Control-Allow-Credentials"] == "true"
        assert headers["Vary"] == "Origin"


def test_partner_domain_requires_https():
    api, _ = _api()
    headers = _balance(api, "http://shop.kettle.example")
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["Vary"] == "Origin"


@pytest.mark.parametrize("origin", ["https://bluekettle.example", "https://shop.coldroastery.example"])
def test_other_sites_sharing_a_name_suffix_are_not_partners(origin):
    api, _ = _api()
    headers = _balance(api, origin)
    assert "Access-Control-Allow-Origin" not in headers
    assert "Access-Control-Allow-Credentials" not in headers


def test_preflight_for_redeem():
    api, ledger = _api()
    ok = api.handle(
        Request(
            "OPTIONS",
            "/v1/redeem",
            {
                "origin": "https://shop.kettle.example",
                "access-control-request-method": "POST",
                "access-control-request-headers": "Content-Type",
            },
        )
    )
    assert ok.status == 204
    assert ok.headers["Access-Control-Allow-Origin"] == "https://shop.kettle.example"
    assert ok.headers["Access-Control-Allow-Methods"] == "GET, POST"
    assert ok.headers["Access-Control-Max-Age"] == "300"
    refused = api.handle(
        Request("OPTIONS", "/v1/redeem", {"origin": "https://kettle.example", "access-control-request-method": "PUT"})
    )
    assert "Access-Control-Allow-Origin" not in refused.headers
    redeemed = api.handle(Request("POST", "/v1/redeem", {"origin": "https://kettle.example"}, 7, {"reward": "latte"}))
    assert redeemed.status == 200 and redeemed.body == {"member": 7, "points": 350}
    assert ledger.redemptions == [(7, "latte")]


def test_preflight_from_a_lookalike_site_is_not_allowed():
    api, _ = _api()
    response = api.handle(
        Request(
            "OPTIONS",
            "/v1/redeem",
            {"origin": "https://mykettle.example", "access-control-request-method": "POST"},
        )
    )
    assert response.status == 204
    assert "Access-Control-Allow-Origin" not in response.headers
