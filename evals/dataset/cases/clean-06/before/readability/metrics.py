"""Text statistics for the readability checker."""

import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENTENCE_END = re.compile(r"[.!?]+(?:\s+|$)")
VOWEL_GROUPS = re.compile(r"[aeiouy]+")


def words(text):
    return WORD.findall(text)


def sentences(text):
    parts = SENTENCE_END.split(text.strip())
    return [p for p in parts if p.strip()]


def syllables(word):
    w = word.lower()
    n = len(VOWEL_GROUPS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(n, 1)


def flesch_reading_ease(text):
    ws = words(text)
    ss = sentences(text)
    if not ws or not ss:
        return None
    syl = sum(syllables(w) for w in ws)
    return round(206.835 - 1.015 * (len(ws) / len(ss)) - 84.6 * (syl / len(ws)), 1)


def top_words(text, n=10, ignore=[]):
    skip = {w.lower() for w in ignore}
    counts = Counter(w.lower() for w in words(text) if w.lower() not in skip)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def long_sentences(text, limit=25):
    return [s for s in sentences(text) if len(words(s)) > limit]
