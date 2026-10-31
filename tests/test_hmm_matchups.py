"""Tests for scripts/hmm_matchups.py: the Franks-style HMM on hand-built geometry."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hmm_matchups import (  # noqa: E402
    STAY,
    WEIGHTS,
    emission_loglik,
    fit_em,
    forward_filter,
    viterbi_paths,
    viterbi_scores,
    wilson,
)

from scbasket.wind import HOOP  # noqa: E402

#: Five attackers standing still, 10 ft apart along the arc, and the ball on attacker 0.
ATTACKERS = np.array([[-20.0, -20.0], [-20.0, -10.0], [-20.0, 0.0], [-20.0, 10.0], [-20.0, 20.0]])


def canonical(k: int, ball: np.ndarray) -> np.ndarray:
    """Where the model expects a defender who guards attacker k."""
    w_o, w_b, w_h = WEIGHTS
    return w_o * ATTACKERS[k] + w_b * ball + w_h * HOOP


def scene(path: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One defender standing exactly at the canonical spot of path[t] on every frame t."""
    T = len(path)
    ball = np.tile(ATTACKERS[0], (T, 1))
    off = np.tile(ATTACKERS, (T, 1, 1))
    dfn = np.array([[canonical(k, ball[t])] for t, k in enumerate(path)])
    return off, dfn, ball


def labels(path: list[int], var: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    off, dfn, ball = scene(path)
    ll = emission_loglik(off, dfn, ball, WEIGHTS, var)
    starts = np.zeros(len(path), bool)
    starts[0] = True
    scores, back = viterbi_scores(ll, starts, STAY)
    causal = scores.argmax(-1)[:, 0]
    whole = viterbi_paths(scores, back, starts)[:, 0]
    filtered = forward_filter(ll, starts, STAY)[:, 0].argmax(-1)
    return causal, whole, filtered


def test_a_defender_glued_to_a_then_b_is_labelled_a_then_b():
    a, b = 1, 3
    want = np.array([a] * 60 + [b] * 60)
    for got in labels(list(want)):
        assert (got == want).all()


def test_a_brief_blip_does_not_switch_but_a_long_stay_does():
    # Attackers 1 and 2 stand 10 ft apart, so their canonical spots 6.2 ft apart; with var 25,
    # standing at 2's spot favours 2 by about 0.77 log units a frame, while leaving 1 and
    # coming back costs about 10 (2 log(0.975 / 0.00625)): 3 frames stay 1, 60 frames switch.
    blip = [1] * 40 + [2] * 3 + [1] * 40
    _, whole, _ = labels(blip, var=25.0)
    assert (whole == 1).all()
    stay = [1] * 40 + [2] * 60
    _, whole, _ = labels(stay, var=25.0)
    assert whole[0] == 1 and whole[-1] == 2


def test_the_label_at_t0_reads_no_frame_after_it():
    rng = np.random.default_rng(1)
    T, t0 = 120, 70
    off = rng.uniform([-40, -24], [0, 24], size=(T, 5, 2))
    ball = rng.uniform([-40, -24], [0, 24], size=(T, 2))
    dfn = rng.uniform([-40, -24], [0, 24], size=(T, 5, 2))
    starts = np.zeros(T, bool)
    starts[[0, 30]] = True
    before = viterbi_scores(emission_loglik(off, dfn, ball, WEIGHTS, 9.0), starts, STAY)[0]
    filt = forward_filter(emission_loglik(off, dfn, ball, WEIGHTS, 9.0), starts, STAY)
    off2, dfn2, ball2 = off.copy(), dfn.copy(), ball.copy()
    off2[t0 + 1:] = rng.uniform(-40, 0, size=off2[t0 + 1:].shape)
    dfn2[t0 + 1:] = rng.uniform(-40, 0, size=dfn2[t0 + 1:].shape)
    ball2[t0 + 1:] = 0.0
    ll2 = emission_loglik(off2, dfn2, ball2, WEIGHTS, 9.0)
    after = viterbi_scores(ll2, starts, STAY)[0]
    filt2 = forward_filter(ll2, starts, STAY)
    assert np.array_equal(before[: t0 + 1], after[: t0 + 1])
    assert np.array_equal(filt[: t0 + 1], filt2[: t0 + 1])
    assert not np.array_equal(filt[t0 + 1:], filt2[t0 + 1:])


def test_em_recovers_the_spread_and_the_weights_it_was_built_with():
    rng = np.random.default_rng(0)
    T = 2000
    off = rng.uniform([-42, -24], [-5, 24], size=(T, 5, 2))
    ball = off[:, 0] + rng.normal(0, 1, size=(T, 2))
    guard = np.repeat(rng.permutation(5)[None], T, axis=0)
    guard[T // 2:, 0] = guard[0, 1]  # one switch half way, onto another defender's man
    mu = (WEIGHTS[0] * off[np.arange(T)[:, None], guard] + WEIGHTS[1] * ball[:, None]
          + WEIGHTS[2] * HOOP)
    dfn = mu + rng.normal(0, 2.0, size=mu.shape)
    starts = np.zeros(T, bool)
    starts[[0, 1000]] = True
    data = [(off, dfn, ball, starts)]
    _, var, _ = fit_em(data, STAY)
    assert abs(np.sqrt(var) - 2.0) < 0.1
    weights, var_w, _ = fit_em(data, STAY, weights=(0.5, 0.2, 0.3), fit_weights=True)
    assert np.allclose(weights, WEIGHTS, atol=0.02)
    assert abs(sum(weights) - 1.0) < 1e-12
    assert abs(np.sqrt(var_w) - 2.0) < 0.1


def test_wilson_interval():
    low, high = wilson(0, 20)
    assert low == 0.0 and 0.1 < high < 0.2
    low, high = wilson(10, 20)
    assert abs((low + high) / 2 - 0.5) < 1e-12
