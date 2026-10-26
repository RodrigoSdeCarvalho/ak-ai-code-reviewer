from __future__ import annotations

DEFAULT_LOCALE = "en"


def normalise(tag: str) -> str:
    """Canonical casing for a language tag: ``pt_br`` -> ``pt-BR``, ``zh-hant-tw`` -> ``zh-Hant-TW``."""
    parts = [part for part in tag.strip().replace("_", "-").split("-") if part]
    if not parts:
        raise ValueError(f"empty language tag: {tag!r}")
    language, *rest = parts
    subtags: list[str] = []
    for part in rest:
        if len(part) == 2 or (len(part) == 3 and part.isdigit()):
            subtags.append(part.upper())
        elif len(part) == 4 and part.isalpha():
            subtags.append(part.title())
        else:
            subtags.append(part.lower())
    return "-".join([language.lower(), *subtags])


def parents(tag: str) -> list[str]:
    """The tag followed by each shorter prefix: ``zh-Hant-TW``, ``zh-Hant``, ``zh``."""
    parts = normalise(tag).split("-")
    return ["-".join(parts[:size]) for size in range(len(parts), 0, -1)]


def fallback_chain(locale: str, default: str = DEFAULT_LOCALE) -> list[str]:
    """Locales to try for a message, most specific first, ending with the default locale."""
    chain = parents(locale)
    for candidate in parents(default):
        if candidate not in chain:
            chain.append(candidate)
    return chain
