"""Uncertainty: cluster bootstrap over cases, paired bootstrap deltas, exact McNemar, Wilson intervals.

The resampling unit is the case: all k samples of a resampled case travel together. The same seed
gives the same resample indices for every metric (common random numbers across metrics and runs).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Sequence

import numpy as np

CI_LEVEL = 0.95


def resample_indices(n_cases: int, n_boot: int, seed: int) -> np.ndarray:
    """(n_boot, n_cases) case indices drawn with replacement."""
    return np.random.default_rng(seed).integers(0, n_cases, size=(n_boot, n_cases))


def case_weights(n_cases: int, n_boot: int, seed: int) -> np.ndarray | None:
    """(n_boot, n_cases) counts of each case in each resample (same draws as `resample_indices`).

    None when there is nothing to resample (n_boot <= 0 or no cases).
    """
    if n_boot <= 0 or n_cases == 0:
        return None
    idx = resample_indices(n_cases, n_boot, seed)
    flat = (idx + np.arange(n_boot)[:, None] * n_cases).ravel()
    return np.bincount(flat, minlength=n_boot * n_cases).reshape(n_boot, n_cases).astype(float)


def percentile_ci(values: np.ndarray) -> tuple[float, float]:
    """Percentile interval at CI_LEVEL, ignoring NaN resamples; (nan, nan) if none are finite."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return math.nan, math.nan
    alpha = (1 - CI_LEVEL) / 2 * 100
    lo, hi = np.percentile(finite, [alpha, 100 - alpha])
    return float(lo), float(hi)


def pooled_ratio(num: np.ndarray, den: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Per-sample micro ratio sum(num) / sum(den) over cases; NaN where the denominator is 0.

    `num`, `den`: (n_cases, n_samples). Without weights returns (n_samples,); with (n_boot, n_cases)
    weights returns (n_boot, n_samples).
    """
    top = num.sum(axis=0) if weights is None else weights @ num
    bottom = den.sum(axis=0) if weights is None else weights @ den
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(bottom > 0, top / np.where(bottom > 0, bottom, 1), np.nan)


def mean_over_samples(per_sample: np.ndarray) -> np.ndarray | float:
    """Mean over the last axis ignoring NaN samples (NaN when all are NaN)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = np.nanmean(per_sample, axis=-1)
    return float(result) if np.ndim(result) == 0 else result


def cluster_bootstrap(
    case_ids: Sequence[str], stat_fn: Callable[[list[str]], float], n_boot: int = 10000, seed: int = 0
) -> tuple[float, float]:
    """95% percentile CI of `stat_fn` over case lists resampled with replacement (repeats kept)."""
    ids = list(case_ids)
    if not ids or n_boot <= 0:
        return math.nan, math.nan
    idx = resample_indices(len(ids), n_boot, seed)
    values = np.array([stat_fn([ids[j] for j in row]) for row in idx], dtype=float)
    return percentile_ci(values)


def bootstrap_p_two_sided(deltas: np.ndarray) -> float:
    """Two-sided bootstrap p-value for delta = 0: 2 x the smaller tail mass, capped at 1."""
    finite = deltas[np.isfinite(deltas)]
    if finite.size == 0:
        return math.nan
    tail = min(np.mean(finite <= 0), np.mean(finite >= 0))
    return float(min(1.0, 2 * tail))


def paired_bootstrap_delta(
    case_ids: Sequence[str],
    stat_a: Callable[[list[str]], float],
    stat_b: Callable[[list[str]], float],
    n_boot: int = 10000,
    seed: int = 0,
) -> dict[str, float]:
    """Delta = stat_b - stat_a (candidate minus baseline) on the same resampled case lists."""
    ids = list(case_ids)
    delta = stat_b(ids) - stat_a(ids)
    idx = resample_indices(len(ids), n_boot, seed)
    deltas = np.empty(n_boot)
    for k, row in enumerate(idx):
        sample = [ids[j] for j in row]
        deltas[k] = stat_b(sample) - stat_a(sample)
    lo, hi = percentile_ci(deltas)
    return {"delta": float(delta), "ci_low": lo, "ci_high": hi, "p_two_sided": bootstrap_p_two_sided(deltas)}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value: binomial test of b vs c discordant pairs at p = 0.5."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials; (0, 1) when n = 0."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)
