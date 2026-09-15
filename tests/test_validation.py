"""Tests for scbasket.validation: rank_auc, spearman, partial_spearman, permutation_pvalue."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scbasket.validation import partial_spearman, permutation_pvalue, rank_auc, spearman


def _brute_force_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Independent O(n^2) reference: count pairs, crediting ties as one half."""
    positive = score[label == 1]
    negative = score[label == 0]
    total = 0.0
    for p in positive:
        for ng in negative:
            if p > ng:
                total += 1.0
            elif p == ng:
                total += 0.5
    return total / (positive.shape[0] * negative.shape[0])


# --------------------------------------------------------------------------- rank_auc


def test_rank_auc_perfect_separation_is_one():
    score = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    label = np.array([0, 0, 0, 1, 1, 1])
    assert rank_auc(score, label) == 1.0


def test_rank_auc_random_labels_is_about_half():
    rng = np.random.default_rng(42)
    score = rng.standard_normal(2000)
    label = rng.integers(0, 2, size=2000)
    result = rank_auc(score, label)
    assert abs(result - 0.5) <= 0.05


def test_rank_auc_with_ties_matches_brute_force_pair_counting():
    score = np.array([1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 4.0, 5.0, 5.0, 6.0])
    label = np.array([0, 0, 1, 0, 1, 0, 1, 1, 0, 1])
    assert rank_auc(score, label) == pytest.approx(_brute_force_auc(score, label))


def test_rank_auc_drops_nan_pairs_before_ranking():
    score = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    label = np.array([0, 0, 1, 1, 1, 1])
    cleaned_score = np.array([1.0, 2.0, 4.0, 5.0, 6.0])
    cleaned_label = np.array([0, 0, 1, 1, 1])
    assert rank_auc(score, label) == rank_auc(cleaned_score, cleaned_label)


def test_rank_auc_returns_nan_with_fewer_than_three_valid_pairs():
    assert np.isnan(rank_auc(np.array([1.0, 2.0]), np.array([0, 1])))


def test_rank_auc_returns_nan_when_label_has_a_single_class():
    score = np.array([1.0, 2.0, 3.0, 4.0])
    label = np.array([0, 0, 0, 0])
    assert np.isnan(rank_auc(score, label))


def test_rank_auc_constant_score_is_one_half():
    score = np.full(10, 3.0)
    label = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    assert rank_auc(score, label) == pytest.approx(0.5)


# --------------------------------------------------------------------------- spearman


def _pandas_spearman(a: np.ndarray, b: np.ndarray) -> float:
    """pandas' own Spearman correlation, without going through scipy.

    `Series.corr(method="spearman")` dispatches to `scipy.stats.spearmanr`,
    and scipy is not a dependency of this repo (nor installed in this venv).
    Spearman correlation is, by definition, the Pearson correlation of the
    ranks, so `Series.rank()` (pandas' own midrank implementation) followed
    by the default Pearson `.corr()` is the exact same computation scipy
    would do, and is still a genuine cross-check: both the ranking and the
    correlation are pandas' independent implementation, not ours.
    """
    return pd.Series(a).rank().corr(pd.Series(b).rank())


def test_spearman_matches_pandas_without_ties():
    rng = np.random.default_rng(1)
    a = rng.standard_normal(200)
    b = rng.standard_normal(200)
    expected = _pandas_spearman(a, b)
    assert spearman(a, b) == pytest.approx(expected, abs=1e-12)


def test_spearman_matches_pandas_with_ties():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 5, size=300).astype(float)  # heavy ties
    b = rng.integers(0, 8, size=300).astype(float)
    expected = _pandas_spearman(a, b)
    assert spearman(a, b) == pytest.approx(expected, abs=1e-12)


def test_spearman_perfect_monotonic_relationship_is_one():
    a = np.linspace(-5.0, 5.0, 50)
    b = a**3  # strictly increasing, non-linear -- Spearman is rank-only
    assert spearman(a, b) == pytest.approx(1.0)


def test_spearman_drops_nan_pairs():
    a = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
    b = np.array([2.0, 3.0, np.nan, 8.0, 10.0])
    cleaned_a = np.array([1.0, 4.0, 5.0])
    cleaned_b = np.array([2.0, 8.0, 10.0])
    assert spearman(a, b) == spearman(cleaned_a, cleaned_b)


def test_spearman_returns_nan_with_fewer_than_three_valid_pairs():
    assert np.isnan(spearman(np.array([1.0, 2.0]), np.array([3.0, 4.0])))


def test_spearman_returns_nan_for_constant_input():
    a = np.full(10, 1.0)
    b = np.arange(10.0)
    assert np.isnan(spearman(a, b))


# --------------------------------------------------------------------- partial_spearman


def test_partial_spearman_near_zero_when_y_depends_only_on_z():
    rng = np.random.default_rng(3)
    z = rng.standard_normal(3000)
    y = 2 * z + 0.1 * rng.standard_normal(3000)  # y ~ z, plus a little noise
    x = rng.standard_normal(3000)  # independent of both y and z
    result = partial_spearman(y, x, z)
    assert abs(result) <= 0.05


def test_partial_spearman_positive_when_x_adds_information_beyond_z():
    rng = np.random.default_rng(4)
    z = rng.standard_normal(3000)
    x = rng.standard_normal(3000)
    y = 2 * z + 3 * x + 0.1 * rng.standard_normal(3000)
    result = partial_spearman(y, x, z)
    assert result > 0.3


def test_partial_spearman_with_a_constant_z_reduces_to_plain_spearman():
    rng = np.random.default_rng(5)
    y = rng.standard_normal(100)
    x = rng.standard_normal(100)
    z = np.full(100, 7.0)
    assert partial_spearman(y, x, z) == pytest.approx(spearman(y, x), abs=1e-9)


def test_partial_spearman_drops_nan_rows():
    y = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    x = np.array([2.0, 3.0, 4.0, np.nan, 6.0])
    z = np.array([1.0, 1.0, 1.0, 1.0, 2.0])
    cleaned_y = np.array([1.0, 2.0, 5.0])
    cleaned_x = np.array([2.0, 3.0, 6.0])
    cleaned_z = np.array([1.0, 1.0, 2.0])
    assert partial_spearman(y, x, z) == partial_spearman(cleaned_y, cleaned_x, cleaned_z)


def test_partial_spearman_returns_nan_with_fewer_than_three_valid_rows():
    y = np.array([1.0, 2.0])
    x = np.array([3.0, 4.0])
    z = np.array([5.0, 6.0])
    assert np.isnan(partial_spearman(y, x, z))


def test_partial_spearman_returns_nan_for_constant_y():
    y = np.full(20, 1.0)
    x = np.arange(20.0)
    z = np.arange(20.0)[::-1]
    assert np.isnan(partial_spearman(y, x, z))


# ------------------------------------------------------------------- permutation_pvalue


def test_permutation_pvalue_reproducible_with_a_fixed_seed():
    values = np.array([0.1, 0.4, 0.2, 0.9, 1.1, 0.3, 0.6, 1.4, 0.8, 1.0, 0.15, 0.95])
    labels = np.array([0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p1 = permutation_pvalue(stat, groups=(labels,), n=500, rng=np.random.default_rng(7))
    p2 = permutation_pvalue(stat, groups=(labels,), n=500, rng=np.random.default_rng(7))
    assert p1 == p2


def test_permutation_pvalue_small_for_an_obvious_effect():
    rng = np.random.default_rng(0)
    values = np.concatenate([rng.normal(0.0, 1.0, 300), rng.normal(3.0, 1.0, 300)])
    labels = np.concatenate([np.zeros(300), np.ones(300)])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p = permutation_pvalue(stat, groups=(labels,), n=2000, rng=np.random.default_rng(1))
    assert p < 0.01


def test_permutation_pvalue_large_for_pure_noise():
    rng = np.random.default_rng(2)
    values = rng.normal(0.0, 1.0, 600)  # same distribution regardless of the label
    labels = np.concatenate([np.zeros(300), np.ones(300)])

    def stat(w):
        return values[w == 1].mean() - values[w == 0].mean()

    p = permutation_pvalue(stat, groups=(labels,), n=2000, rng=np.random.default_rng(3))
    assert p > 0.1


def test_permutation_pvalue_precomputed_mode_matches_manual_calculation():
    null = np.array([1.0, 2.0, 3.0, 4.0, 10.0, 6.0, 7.0])
    observed = 5.0
    result = permutation_pvalue(observed, null)
    expected = (np.sum(null >= observed) + 1) / (null.shape[0] + 1)
    assert result == pytest.approx(expected)


def test_permutation_pvalue_raises_on_mismatched_group_lengths():
    with pytest.raises(ValueError):
        permutation_pvalue(lambda a, b: 0.0, groups=(np.zeros(5), np.zeros(6)))


def test_permutation_pvalue_returns_nan_with_fewer_than_three_points():
    p = permutation_pvalue(lambda a: a.mean(), groups=(np.array([1.0, 2.0]),))
    assert np.isnan(p)


def test_permutation_pvalue_precomputed_mode_returns_nan_with_a_short_null():
    assert np.isnan(permutation_pvalue(5.0, np.array([1.0, 2.0])))


def test_permutation_pvalue_returns_nan_when_observed_statistic_is_nan():
    assert np.isnan(permutation_pvalue(float("nan"), np.array([1.0, 2.0, 3.0])))
