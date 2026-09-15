"""Tests for scbasket.quality.sigma_from_pred_error (D8).

The rest of quality.py (profile_game, profile_dataset, distance_error, distance_with_error)
streams the real tracking JSON and has no unit-testable surface without it; it is exercised
by scripts/profile_quality.py against the real dataset and is out of scope here.
"""

from __future__ import annotations

import numpy as np
import pytest

from scbasket.quality import RAYLEIGH_90_FACTOR, sigma_from_pred_error


def test_sigma_from_pred_error_divides_by_the_rayleigh_90_factor():
    pred_error = np.array([0.0, 2.146, 4.292, 10.73])
    sigma = sigma_from_pred_error(pred_error)
    np.testing.assert_allclose(sigma, [0.0, 1.0, 2.0, 5.0], rtol=1e-12)
    assert RAYLEIGH_90_FACTOR == pytest.approx(2.146)


def test_sigma_from_pred_error_is_linear_and_preserves_shape():
    rng = np.random.default_rng(0)
    pred_error = rng.uniform(0.0, 6.0, size=(4, 10))
    sigma = sigma_from_pred_error(pred_error)
    assert sigma.shape == pred_error.shape
    assert sigma.dtype == np.float64
    np.testing.assert_allclose(sigma, pred_error / RAYLEIGH_90_FACTOR)
    # Doubling predError doubles sigma: it is a plain scale factor, not a curve.
    np.testing.assert_allclose(sigma_from_pred_error(2 * pred_error), 2 * sigma)


def test_sigma_from_pred_error_accepts_a_python_scalar():
    assert sigma_from_pred_error(2.146) == pytest.approx(1.0)
