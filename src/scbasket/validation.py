"""Rank-based validation metrics for scbasket.

Pure numpy, no sklearn/scipy: the model is graded against ground truth
(`contestLevel`, `shotQuality`) with rank statistics computed from first
principles, because the acceptance criteria in the project plan (P1.5, P2.3)
need exact control over tie handling and the permutation scheme.

This module currently holds the four statistics helpers below (`rank_auc`,
`spearman`, `partial_spearman`, `permutation_pvalue`). `release_features`,
`calibrate`, `pick_windows` and `break_points` -- the release-feature
extraction and calibration/validation pipeline built on top of
`control.py` -- are appended below them by a later change; nothing in this
module imports from `control.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def _midranks(x: np.ndarray) -> np.ndarray:
    """1-based ranks of `x`, averaging ranks within ties (midrank convention).

    Matches `pandas.Series.rank()`'s default (`method="average"`), which is
    what the Mann-Whitney U <-> AUC identity and pandas' own Spearman
    implementation both rely on. Fully vectorized: no Python loop over ties.
    """
    order = np.argsort(x, kind="mergesort")
    plain_ranks = np.empty(x.shape[0], dtype=float)
    plain_ranks[order] = np.arange(1, x.shape[0] + 1, dtype=float)
    _, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.zeros(counts.shape[0], dtype=float)
    np.add.at(sums, inverse, plain_ranks)
    return (sums / counts)[inverse]


def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two already-cleaned 1-D arrays; NaN if either is constant."""
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a**2).sum() * (b**2).sum())
    if denom == 0:
        return float("nan")
    return float((a * b).sum() / denom)


def _ols_residuals(z: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Residuals of the OLS regression of `target` on `z` (with intercept).

    If `z` is constant there is nothing to regress on: the residual is just
    `target`'s deviation from its own mean, i.e. no control is applied.
    """
    z_centered = z - z.mean()
    var_z = (z_centered**2).sum()
    target_centered = target - target.mean()
    if var_z == 0:
        return target_centered
    slope = (z_centered * target_centered).sum() / var_z
    return target_centered - slope * z_centered


def rank_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Area under the ROC curve, computed from ranks (Mann-Whitney U statistic).

    `label` must be binary (0/1 or bool). AUC is the probability that a
    randomly drawn positive (`label == 1`) outranks a randomly drawn
    negative, with tied scores counted as one half -- no sklearn, no scipy.
    Ties use the midrank convention (`_midranks`).

    NaN policy: rows where `score` or `label` is NaN are dropped pairwise
    before ranking. Returns NaN if fewer than 3 valid pairs remain, or if
    `label` has only one class (AUC is undefined with no negatives, or no
    positives, to compare against). A constant `score` is NOT a degenerate
    case: every pair ties and the midrank formula correctly returns 0.5.
    """
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=float)
    valid = ~(np.isnan(score) | np.isnan(label))
    score, label = score[valid], label[valid]

    if score.shape[0] < 3:
        return float("nan")

    positive = label == 1
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")

    ranks = _midranks(score)
    r1 = ranks[positive].sum()
    u1 = r1 - n1 * (n1 + 1) / 2
    return float(u1 / (n1 * n0))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation, matching `pandas.Series.corr(method="spearman")`.

    Ties use the midrank convention (`_midranks`), the same one pandas'
    `.rank()` uses by default, then it is the Pearson correlation of the two
    rank arrays.

    NaN policy: rows where `a` or `b` is NaN are dropped pairwise. Returns
    NaN if fewer than 3 valid pairs remain, or if `a` or `b` is constant
    (no variance to correlate).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    valid = ~(np.isnan(a) | np.isnan(b))
    a, b = a[valid], b[valid]

    if a.shape[0] < 3:
        return float("nan")
    if np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")

    return _pearson_corr(_midranks(a), _midranks(b))


def partial_spearman(y: np.ndarray, x: np.ndarray, z: np.ndarray) -> float:
    """Partial Spearman correlation of `y` and `x` controlling for `z`, via rank residuals.

    Answers "does `x` carry information about `y` beyond `z`". Method (as
    specified in the project plan, not the textbook first-order-partial
    formula): rank-transform `y`, `x` and `z` (midranks), regress ranked `y`
    and ranked `x` on ranked `z` by ordinary least squares, and correlate
    the two residuals (Pearson).

    NaN policy: rows where any of `y`, `x`, `z` is NaN are dropped rowwise.
    Returns NaN if fewer than 3 valid rows remain, or if `y` or `x` is
    constant (nothing to correlate). A constant `z` is NOT a degenerate
    case: `_ols_residuals` then applies no control and this reduces to
    plain `spearman(y, x)`, which is the mathematically correct answer for
    "controlling for a variable that never varies". If the residuals of `y`
    or `x` end up constant (e.g. `y` is an exact monotonic function of `z`,
    so ranking removes all of its variance), the correlation is undefined
    and NaN is returned.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    valid = ~(np.isnan(y) | np.isnan(x) | np.isnan(z))
    y, x, z = y[valid], x[valid], z[valid]

    if y.shape[0] < 3:
        return float("nan")
    if np.all(y == y[0]) or np.all(x == x[0]):
        return float("nan")

    ry, rx, rz = _midranks(y), _midranks(x), _midranks(z)
    resid_y = _ols_residuals(rz, ry)
    resid_x = _ols_residuals(rz, rx)
    return _pearson_corr(resid_y, resid_x)


def permutation_pvalue(
    stat: Callable[..., float] | float,
    groups: Sequence[np.ndarray] | np.ndarray,
    n: int = 2000,
    rng: np.random.Generator | None = None,
) -> float:
    """One-sided permutation p-value: the share of the null draws >= the observed statistic.

    Two calling conventions, chosen to cover both places this project needs a
    permutation test (P1.5, P2.3), which shuffle fundamentally different
    things:

    1. `stat` callable, `groups` a sequence of 1-D arrays of equal length
       that are the thing being permuted (everything else `stat` needs is
       captured by closure). Each of the `n` draws applies one shared random
       permutation index to every array in `groups` (so their relative order
       to each other survives, only their pairing to whatever is captured by
       closure is broken), then calls `stat(*permuted_groups)`. The observed
       statistic is `stat(*groups)` (unpermuted). This is P1.5's case:
       `permutation_pvalue(lambda x: partial_spearman(y, x, z), groups=(x,))`
       shuffles `x` while `y` and `z` (closed over) stay fixed. It is also
       the classic two-sample label-shuffle test: pool the values into one
       array `v`, build a 0/1 window-label array `w`, and call
       `permutation_pvalue(lambda w: v[w == 1].mean() - v[w == 0].mean(),
       groups=(w,))` -- P2.3's "does the screener's `created` rise between
       the two windows" case.
    2. `stat` a plain number (the already-computed observed statistic) and
       `groups` the already-simulated null distribution (an array of one
       statistic value per permutation draw). `n` and `rng` are ignored.
       This exists for callers whose shuffle needs domain logic this module
       has no business knowing (P2.3's actual `created` aggregation lives in
       `scripts/space_creation.py` and reshuffles window labels over
       frame-level data, not a plain array this module could permute
       generically); they run their own permutation loop and hand the
       resulting numbers here just for the p-value arithmetic.

    Both of this project's uses ask for a one-sided test ("> 0", "rises"),
    so the p-value is always `P(null >= observed)`, never two-sided.

    Reproducibility: pass an explicit `rng` (a `numpy.random.Generator`,
    e.g. `np.random.default_rng(seed)`); the same seed gives the same
    p-value. Without one, a fresh, unseeded generator is used.

    NaN policy: returns NaN if fewer than 3 data points are available to
    permute (mode 1: `len(groups[0]) < 3`; mode 2: `len(groups) < 3`), if the
    observed statistic is NaN, or if fewer than 3 non-NaN null draws remain
    (NaN null draws, e.g. from a degenerate shuffle, are dropped). Uses the
    standard add-one correction so the p-value is never exactly 0.
    """
    if callable(stat):
        arrays = [np.asarray(g) for g in groups]
        if not arrays or arrays[0].shape[0] < 3:
            return float("nan")
        length = arrays[0].shape[0]
        if any(a.shape[0] != length for a in arrays):
            raise ValueError("all arrays in `groups` must have the same length")

        rng = np.random.default_rng() if rng is None else rng
        observed = float(stat(*arrays))
        null = np.empty(n, dtype=float)
        for i in range(n):
            perm = rng.permutation(length)
            null[i] = stat(*(a[perm] for a in arrays))
    else:
        observed = float(stat)
        null = np.asarray(groups, dtype=float).ravel()
        if null.shape[0] < 3:
            return float("nan")

    if np.isnan(observed):
        return float("nan")

    null = null[~np.isnan(null)]
    if null.shape[0] < 3:
        return float("nan")

    exceed = int(np.sum(null >= observed))
    return float((exceed + 1) / (null.shape[0] + 1))
