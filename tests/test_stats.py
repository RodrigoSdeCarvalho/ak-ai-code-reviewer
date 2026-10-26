import time

import numpy as np
import pytest

from aireview.evals.stats import (
    case_weights,
    cluster_bootstrap,
    mcnemar_exact,
    paired_bootstrap_delta,
    pooled_ratio,
    resample_indices,
    wilson_ci,
)


def test_mcnemar_known_values():
    assert mcnemar_exact(0, 6) == pytest.approx(0.03125)
    assert mcnemar_exact(6, 0) == pytest.approx(0.03125)
    assert mcnemar_exact(1, 9) == pytest.approx(2 * 11 / 1024)
    assert mcnemar_exact(3, 3) == 1.0
    assert mcnemar_exact(0, 0) == 1.0


def test_wilson_ci():
    assert wilson_ci(0, 0) == (0.0, 1.0)
    lo, hi = wilson_ci(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0 and 0 < hi < 0.35


def test_case_weights_match_resample_indices():
    idx = resample_indices(7, 50, seed=3)
    w = case_weights(7, 50, seed=3)
    assert w.shape == (50, 7)
    assert (w.sum(axis=1) == 7).all()
    for row, counts in zip(idx, w, strict=True):
        assert (np.bincount(row, minlength=7) == counts).all()
    assert case_weights(0, 50, 0) is None and case_weights(5, 0, 0) is None


def test_cluster_bootstrap_contains_point_and_is_deterministic():
    values = {f"c{i}": float(i % 4 == 0) for i in range(60)}

    def mean(ids):
        assert len(ids) == 60
        return float(np.mean([values[c] for c in ids]))

    ids = list(values)
    ci = cluster_bootstrap(ids, mean, n_boot=2000, seed=1)
    assert ci == cluster_bootstrap(ids, mean, n_boot=2000, seed=1)
    assert ci[0] <= mean(ids) <= ci[1]
    assert ci[0] < ci[1]


def test_cluster_bootstrap_resamples_with_repeats():
    seen_repeat = []
    cluster_bootstrap(["a", "b", "c"], lambda ids: seen_repeat.append(len(set(ids)) < 3) or 0.0, n_boot=50)
    assert any(seen_repeat)


def test_paired_delta():
    ids = [f"c{i}" for i in range(30)]
    base = {c: float(i % 2) for i, c in enumerate(ids)}

    def a(sample):
        return float(np.mean([base[c] for c in sample]))

    same = paired_bootstrap_delta(ids, a, a, n_boot=500, seed=0)
    assert same["delta"] == 0 and same["ci_low"] == 0 and same["ci_high"] == 0
    assert same["p_two_sided"] == 1.0
    shifted = paired_bootstrap_delta(ids, a, lambda s: a(s) + 0.2, n_boot=500, seed=0)
    assert shifted["delta"] == pytest.approx(0.2)
    assert shifted["ci_low"] == pytest.approx(0.2) and shifted["p_two_sided"] == 0.0


def test_pooled_ratio_and_vectorized_speed():
    rng = np.random.default_rng(0)
    num = rng.integers(0, 3, size=(60, 3)).astype(float)
    den = num + rng.integers(0, 3, size=(60, 3))
    assert np.allclose(pooled_ratio(num, den), num.sum(0) / den.sum(0))
    assert np.isnan(pooled_ratio(np.zeros((2, 1)), np.zeros((2, 1)))).all()
    start = time.perf_counter()
    boot = pooled_ratio(num, den, case_weights(60, 10000, 0))
    assert boot.shape == (10000, 3)
    assert time.perf_counter() - start < 2


def test_python_stat_bootstrap_is_fast_enough():
    ids = [f"c{i}" for i in range(60)]
    start = time.perf_counter()
    cluster_bootstrap(ids, len, n_boot=10000, seed=0)
    assert time.perf_counter() - start < 2
