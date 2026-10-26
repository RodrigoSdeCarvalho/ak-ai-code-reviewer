import json

from i18n.bundles import build_bundle, missing_report, render
from i18n.catalog import RedisCatalog
from i18n.locales import fallback_chain, normalise, parents


class CountingRedis:
    def __init__(self, hashes: dict[str, dict[str, str]]) -> None:
        self.hashes = {name: dict(fields) for name, fields in hashes.items()}
        self.calls = 0

    def hget(self, name: str, key: str) -> str | None:
        self.calls += 1
        return self.hashes.get(name, {}).get(key)

    def hmget(self, name: str, keys: list[str]) -> list[str | None]:
        self.calls += 1
        fields = self.hashes.get(name, {})
        return [fields.get(key) for key in keys]

    def hexists(self, name: str, key: str) -> bool:
        self.calls += 1
        return key in self.hashes.get(name, {})

    def hset(self, name: str, key: str, value: str) -> int:
        self.calls += 1
        fields = self.hashes.setdefault(name, {})
        added = key not in fields
        fields[key] = value
        return int(added)

    def hdel(self, name: str, *keys: str) -> int:
        self.calls += 1
        fields = self.hashes.get(name, {})
        return sum(1 for key in keys if fields.pop(key, None) is not None)


CART = {
    "i18n:pt-BR": {"cart.title": "Carrinho"},
    "i18n:pt": {"cart.title": "Cesto", "cart.empty": "O cesto está vazio", "cart.items": "{count} artigos"},
    "i18n:en": {
        "cart.title": "Cart",
        "cart.empty": "Your cart is empty",
        "cart.items": "{count} items",
        "cart.promo": "Promo code",
    },
}


def test_bundle_makes_one_round_trip_per_locale_in_the_chain():
    keys = [f"checkout.field{n}" for n in range(300)]
    redis = CountingRedis(
        {
            "i18n:pt-BR": {key: f"BR {key}" for key in keys[:30]},
            "i18n:pt": {key: f"PT {key}" for key in keys[:250]},
            "i18n:en": {key: f"EN {key}" for key in keys[:295]},
        }
    )
    bundle = build_bundle(RedisCatalog(redis), "pt-BR", keys)
    assert bundle.messages["checkout.field0"] == "BR checkout.field0"
    assert bundle.messages["checkout.field100"] == "PT checkout.field100"
    assert bundle.messages["checkout.field290"] == "EN checkout.field290"
    assert len(bundle.missing) == 5
    assert redis.calls <= 3


def test_fallback_order_sources_and_missing_keys():
    catalog = RedisCatalog(CountingRedis(CART))
    keys = ["cart.title", "cart.empty", "cart.items", "cart.promo", "cart.gift", "cart.title"]
    bundle = build_bundle(catalog, "pt_br", keys)
    assert bundle.locale == "pt-BR"
    assert bundle.messages == {
        "cart.title": "Carrinho",
        "cart.empty": "O cesto está vazio",
        "cart.items": "{count} artigos",
        "cart.promo": "Promo code",
        "cart.gift": "cart.gift",
    }
    assert bundle.sources == {"cart.title": "pt-BR", "cart.empty": "pt", "cart.items": "pt", "cart.promo": "en"}
    assert bundle.missing == ("cart.gift",)
    assert bundle.fallback_keys() == ["cart.empty", "cart.items", "cart.promo"]
    assert render(bundle, "cart.items", count=3) == "3 artigos"
    assert json.loads(bundle.to_json())["locale"] == "pt-BR"


def test_default_locale_bundle_and_missing_report():
    catalog = RedisCatalog(CountingRedis(CART))
    english = build_bundle(catalog, "en", ["cart.title", "cart.gift"])
    assert english.messages == {"cart.title": "Cart", "cart.gift": "cart.gift"}
    assert english.fallback_keys() == []
    french = build_bundle(catalog, "fr-CA", ["cart.empty", "cart.wrap"])
    assert french.sources == {"cart.empty": "en"}
    assert missing_report([english, french]) == {"en": ["cart.gift"], "fr-CA": ["cart.wrap"]}


def test_locale_tags_and_chains():
    assert normalise("pt_br") == "pt-BR"
    assert normalise(" zh-hant-tw ") == "zh-Hant-TW"
    assert normalise("es-419") == "es-419"
    assert parents("zh-Hant-TW") == ["zh-Hant-TW", "zh-Hant", "zh"]
    assert fallback_chain("pt-BR") == ["pt-BR", "pt", "en"]
    assert fallback_chain("en-GB") == ["en-GB", "en"]
    assert fallback_chain("fr-CA", "en-US") == ["fr-CA", "fr", "en-US", "en"]
