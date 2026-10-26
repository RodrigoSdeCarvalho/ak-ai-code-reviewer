from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from i18n.catalog import MessageCatalog


@dataclass(frozen=True)
class Bundle:
    locale: str
    messages: dict[str, str]
    missing: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps({"locale": self.locale, "messages": self.messages}, ensure_ascii=False, sort_keys=True)


def build_bundle(catalog: MessageCatalog, locale: str, keys: Sequence[str]) -> Bundle:
    """Collect the translations a page needs. A key without a translation renders as the key itself."""
    wanted = list(dict.fromkeys(keys))
    found = catalog.get_many(locale, wanted)
    messages = {key: found.get(key, key) for key in wanted}
    missing = tuple(key for key in wanted if key not in found)
    return Bundle(locale=locale, messages=messages, missing=missing)


def render(bundle: Bundle, key: str, **params: object) -> str:
    template = bundle.messages.get(key, key)
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template


def missing_report(bundles: Sequence[Bundle]) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {}
    for bundle in bundles:
        if bundle.missing:
            report.setdefault(bundle.locale, []).extend(bundle.missing)
    return {locale: sorted(set(keys)) for locale, keys in sorted(report.items())}
