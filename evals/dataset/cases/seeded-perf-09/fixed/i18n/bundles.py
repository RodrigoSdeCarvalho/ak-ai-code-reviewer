from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from i18n.catalog import MessageCatalog
from i18n.locales import DEFAULT_LOCALE, fallback_chain


@dataclass(frozen=True)
class Bundle:
    locale: str
    messages: dict[str, str]
    missing: tuple[str, ...]
    sources: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"locale": self.locale, "messages": self.messages}, ensure_ascii=False, sort_keys=True)

    def fallback_keys(self) -> list[str]:
        """Keys served from a parent or default locale instead of the requested one."""
        return sorted(key for key, source in self.sources.items() if source != self.locale)


def build_bundle(
    catalog: MessageCatalog,
    locale: str,
    keys: Sequence[str],
    default_locale: str = DEFAULT_LOCALE,
) -> Bundle:
    """Collect the translations a page needs.

    A key missing in the requested locale is looked up in its parent locales and then in the default
    locale (``pt-BR`` -> ``pt`` -> ``en``). A key without a translation anywhere renders as the key itself.
    """
    chain = fallback_chain(locale, default_locale)
    messages: dict[str, str] = {}
    sources: dict[str, str] = {}
    remaining = list(dict.fromkeys(keys))
    for candidate in chain:
        if not remaining:
            break
        found = catalog.get_many(candidate, remaining)
        for key, text in found.items():
            messages[key] = text
            sources[key] = candidate
        remaining = [key for key in remaining if key not in found]
    for key in remaining:
        messages[key] = key
    return Bundle(locale=chain[0], messages=messages, missing=tuple(remaining), sources=sources)


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
