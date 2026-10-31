"""Cross-check the provider's matchups with a hidden Markov model after Franks et al. 2015 (14.f 1).

Usage: uv run python scripts/hmm_matchups.py [--root DIR] [--cache DIR] [--out DIR]

The entry's "man left" is the attacker the provider's `matchups` table assigns, at the drive's
start frame r0, to the off-ball defender nearest the ball (`scbasket.help_kinds`). That table
was never checked against ground truth. This script infers who guards whom from positions
alone, with the model of Franks, Miller, Bornn and Goldsberry (2015), "Characterizing the
spatial structure of defensive skill in professional basketball", Annals of Applied
Statistics 9(1) 94-121, arXiv:1405.0231 (section 2, read with pdftotext on 2026-10-31), and
compares the two. Like every module of the entry it names positions and distances, never
intentions: a label is "the attacker the model places this defender with", nothing more.

THE MODEL, FROZEN BEFORE THE RUN ON THE DRIVES (2026-10-31)

- Hidden state: for each defender j, the attacker k (slot 0-4) he is placed with. Each
  defender is an independent HMM, as in the paper; two defenders may share an attacker.
- Emission: D_tj | k ~ N(mu_tk, sigma^2 I), isotropic as in the paper, with
  mu_tk = 0.62 O_tk + 0.11 B_t + 0.27 H (attacker, ball, hoop: the paper's published
  weights, section 2.2, "stable across games", +-0.02 / 0.01 / 0.02). H is `wind.HOOP`, B the
  ball's floor position, all in the attacking frame of the cache.
- Transition: stay STAY = 0.975 per frame, (1 - STAY) / 4 to each other attacker. The paper
  reports 0.96 to 0.99 at 25 frames per second; 0.975 is the midpoint. Our cache is 25 Hz
  (`wind.FPS`), so the per-frame scaling STAY_25HZ ** (25 / FPS) is the identity here.
  Initial state uniform (1 / 5).
- Fitted on our frames: sigma^2 ONLY, by EM (forward-backward E-step, the weights and STAY
  held fixed), on every half-court frame (all ten players at x < 0, as the paper restricts
  to the offensive half court) of every game, in contiguous segments of one possession and
  one lineup. sigma^2 is one number for the whole dataset: it cannot carry the label of any
  one drive. EM starts at VAR_INIT and stops when sigma^2 moves by less than EM_TOL
  (relative).
- Segment ("possession") for the labels: the run of contiguous frames of one possession and
  one lineup (`frames.velocity_runs`), whatever the half.
- The label at the drive's start r0 is CAUSAL: the Viterbi path computed on the segment's
  frames from its first row TO r0 only, read at r0 (the argmax of the max-product score at
  r0, which is the last state of that truncated path). The posterior is the forward filter
  P(state at r0 | frames up to r0). No frame after r0 enters a label, so neither the man's
  position at 2.0 s nor any defender's displacement toward him (the measured quantity) can
  decide it; `tests/test_hmm_matchups.py` checks that rewriting the frames after r0 leaves
  the label and the posterior at r0 unchanged.

THE QUESTIONS, FROZEN BEFORE THE RUN

On the committed near-help drives of the headline (`help_kinds.near_committed`, 246), on the
near reference (`near_ref`, 199) and on every drive whose nearest has a man and a 2.0 s
window (`near_status == "ok"`, the context):

  Q1. Agreement: the share of drives where the HMM's causal label at r0 for the helper (the
      nearest) is the provider's raw man at r0, the man left. Wilson 95 % interval. Beside
      it: chance, 1 in 5; the existing closest-defender baseline of `near_matchup_coherence.csv`
      (the helper is the defender closest to the man left at r0; recomputed here and asserted
      equal to the CSV); the closest attacker to the helper at r0 (the HMM without ball, hoop
      or memory); and the HMM's label 1.0 s before r0 (PRE_FRAMES), when the helper may not
      yet stand in help.
  Q2. Ambiguity: the share of drives where the filtered posterior of the provider's man is
      below AMBIGUOUS_BELOW = 0.5 (the model finds him less likely than not). Also reported,
      not read: below CONFIDENT_FROM = 0.9.
  Q3. The headline re-run on the drives where the HMM agrees (committed and reference alike),
      through the SAME code path as `help_kinds.py`: `drive_kinds` -> `kind_help_table` ->
      `rotation.rotation_table` -> `second_help.summarise` / `second_help.contrast`. The
      unrestricted run is asserted equal to `help_kinds_summary.csv` (n, mean, CI to 1e-9)
      before anything is written. Reading: `help_kinds.reading` on the committed group's own
      1.5 s interval (ABSENCE if it holds 0 or lies below, ROTATION if above, INCONCLUSIVE
      under 40 drives or a CI wider than +-1 ft); the contrast is reported, not read, as in
      the headline.

Sensitivities, reported and never the result: STAY 0.96 and 0.99 (same sigma^2), and the
three weights fitted by EM with sigma^2 (constrained least squares, the paper's M-step).

WHAT WOULD MAKE AN AGREEMENT VANISH (named before trusting one)

- The helper already stands in help at r0: the model then places him with the ball handler
  and disagrees on timing, not on identity. The 1.0 s-before label separates the two.
- Both the provider and the model may be proximity rules: if the HMM agrees no more than the
  closest attacker does, it adds nothing to proximity. And if the provider's own table comes
  from a model of this family, agreement is consistency between two similar models, not
  validation against truth. Neither can be tested without video; both are reported as limits.
- Q3 drops the disagreements: if agreement were near 100 % the re-run would equal the
  headline by construction, so its n is printed next to the full n.

Writes to {out}:
  hmm_matchups.csv          one row per near-ok drive: groups, the provider's man, the HMM's
                            label and posterior under every config, the baselines' labels
  hmm_matchups_summary.csv  tidy: section (fit | frames | agreement | ambiguous | headline),
                            config, group, horizon, series, n, k, value, ci_low, ci_high,
                            reading, note
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd
from help_kinds import CLAIM, reading
from second_help import DATA, INTERIM, REPORTS, contrast, summarise

from scbasket.frames import N_SIDE, GameFrames, get_or_build, velocity_runs
from scbasket.help_kinds import drive_kinds, kind_help_table
from scbasket.io import Dataset
from scbasket.rotation import HEADLINE_HORIZON, ROTATION_HORIZONS, rotation_table
from scbasket.wind import FPS, HELP_FT, HOOP, _row_of, help_table

#: Franks et al. 2015, section 2.2: attacker, ball, hoop.
WEIGHTS = (0.62, 0.11, 0.27)
#: Per-frame probability of staying with the same attacker at 25 Hz (published 0.96 to 0.99).
STAY_25HZ = 0.975
STAY = STAY_25HZ ** (25.0 / FPS)
STAY_SENSITIVITY = (0.96, 0.99)
VAR_INIT = 9.0  # ft^2, a 3 ft spread to start EM from
EM_TOL = 1e-4
EM_MAX_ITER = 200
AMBIGUOUS_BELOW = 0.5
CONFIDENT_FROM = 0.9
PRE_FRAMES = 25  # the label 1.0 s before the drive's start
CHANCE = 1.0 / N_SIDE
Z95 = 1.959963984540054


# --------------------------------------------------------------------------- the model


def emission_loglik(off: np.ndarray, dfn: np.ndarray, ball: np.ndarray,
                    weights: tuple[float, float, float], var: float) -> np.ndarray:
    """(T, J, K) log density of defender j's position if he guards attacker k.

    `off` (T, K, 2) attackers, `dfn` (T, J, 2) defenders, `ball` (T, 2); feet.
    """
    w_o, w_b, w_h = weights
    mu = w_o * off + w_b * ball[:, None, :] + w_h * HOOP
    d2 = ((dfn[:, :, None, :] - mu[:, None, :, :]) ** 2).sum(-1)
    return -d2 / (2.0 * var) - math.log(2.0 * math.pi * var)


def _scaled(loglik: np.ndarray) -> np.ndarray:
    """Likelihoods divided by their largest value per (t, j): finite, the largest equal to 1."""
    return np.exp(loglik - loglik.max(axis=-1, keepdims=True))


def forward_filter(loglik: np.ndarray, starts: np.ndarray, stay: float) -> np.ndarray:
    """(T, J, K) filtered posteriors P(state at t | frames of the segment up to t).

    `starts[t]` opens a new segment (uniform prior). With equal off-diagonal transitions the
    predicted prior is stay * p + move * (1 - p).
    """
    T, J, K = loglik.shape
    move = (1.0 - stay) / (K - 1)
    lik = _scaled(loglik)
    post = np.empty_like(lik)
    p = np.full((J, K), 1.0 / K)
    for t in range(T):
        prior = np.full((J, K), 1.0 / K) if starts[t] else stay * p + move * (1.0 - p)
        q = prior * lik[t]
        p = q / q.sum(axis=-1, keepdims=True)
        post[t] = p
    return post


def backward_pass(loglik: np.ndarray, starts: np.ndarray, stay: float) -> np.ndarray:
    """(T, J, K) normalised backward messages, reset at every segment's last frame."""
    T, J, K = loglik.shape
    move = (1.0 - stay) / (K - 1)
    lik = _scaled(loglik)
    ends = np.append(starts[1:], True)
    beta = np.empty_like(lik)
    b = np.ones((J, K))
    for t in range(T - 1, -1, -1):
        if ends[t]:
            b = np.ones((J, K))
        else:
            m = lik[t + 1] * b
            b = stay * m + move * (m.sum(axis=-1, keepdims=True) - m)
            b = b / b.sum(axis=-1, keepdims=True)
        beta[t] = b
    return beta


def smoothed(loglik: np.ndarray, starts: np.ndarray, stay: float) -> np.ndarray:
    """(T, J, K) posteriors given the whole segment: for the EM fit only, never a label."""
    g = forward_filter(loglik, starts, stay) * backward_pass(loglik, starts, stay)
    return g / g.sum(axis=-1, keepdims=True)


def viterbi_scores(loglik: np.ndarray, starts: np.ndarray,
                   stay: float) -> tuple[np.ndarray, np.ndarray]:
    """Max-product forward pass: (T, J, K) scores (log, max 0 per row) and back pointers.

    `scores[t].argmax(-1)` is the last state of the Viterbi path of the segment truncated at
    t: the causal label, which reads no frame after t.
    """
    T, J, K = loglik.shape
    log_a = np.full((K, K), math.log((1.0 - stay) / (K - 1)))
    np.fill_diagonal(log_a, math.log(stay))
    scores = np.empty_like(loglik)
    back = np.zeros((T, J, K), np.int8)
    s = np.zeros((J, K))
    for t in range(T):
        if starts[t]:
            s = loglik[t] - math.log(K)
            back[t] = np.arange(K)
        else:
            cand = s[:, :, None] + log_a  # (J, from, to)
            back[t] = cand.argmax(axis=1)
            s = cand.max(axis=1) + loglik[t]
        s = s - s.max(axis=-1, keepdims=True)
        scores[t] = s
    return scores, back


def viterbi_paths(scores: np.ndarray, back: np.ndarray, starts: np.ndarray) -> np.ndarray:
    """(T, J) Viterbi path of every whole segment (reads the segment's future: context only)."""
    T, J, _ = scores.shape
    ends = np.append(starts[1:], True)
    path = np.empty((T, J), np.int8)
    cur = np.zeros(J, np.int64)
    for t in range(T - 1, -1, -1):
        cur = scores[t].argmax(axis=-1) if ends[t] else back[t + 1, np.arange(J), cur]
        path[t] = cur
    return path


def sufficient_stats(off: np.ndarray, dfn: np.ndarray, ball: np.ndarray,
                     gamma: np.ndarray) -> np.ndarray:
    """EM statistics with the hoop as origin: D - H = w_o (O - H) + w_b (B - H) + noise."""
    u, v, r = off - HOOP, ball - HOOP, dfn - HOOP
    n_def = dfn.shape[1]
    gk = gamma.sum(axis=1)  # (T, K)
    return np.array([
        np.einsum("tk,tkc,tkc->", gk, u, u),
        np.einsum("tk,tkc,tc->", gk, u, v),
        n_def * np.einsum("tc,tc->", v, v),
        np.einsum("tjk,tkc,tjc->", gamma, u, r),
        np.einsum("tjc,tc->", r, v),
        np.einsum("tjc,tjc->", r, r),
        float(gamma.shape[0] * n_def),
    ])


def m_step(stats: np.ndarray, weights: tuple[float, float, float],
           fit_weights: bool) -> tuple[tuple[float, float, float], float]:
    """sigma^2 (and the weights, constrained to sum 1, when `fit_weights`) from the stats."""
    uu, uv, vv, ur, vr, rr, n = stats
    if fit_weights:
        w_o, w_b = np.linalg.solve([[uu, uv], [uv, vv]], [ur, vr])
    else:
        w_o, w_b = weights[0], weights[1]
    sse = rr - 2 * w_o * ur - 2 * w_b * vr + w_o**2 * uu + 2 * w_o * w_b * uv + w_b**2 * vv
    return (float(w_o), float(w_b), float(1.0 - w_o - w_b)), float(sse / (2.0 * n))


def fit_em(data: list[tuple], stay: float, weights=WEIGHTS, fit_weights: bool = False,
           var: float = VAR_INIT) -> tuple[tuple[float, float, float], float, int]:
    """EM on `data`, a list of (off, dfn, ball, starts): sigma^2, and the weights if asked."""
    done, it = False, 0
    while not done and it < EM_MAX_ITER:
        it += 1
        stats = np.zeros(7)
        for off, dfn, ball, starts in data:
            gamma = smoothed(emission_loglik(off, dfn, ball, weights, var), starts, stay)
            stats += sufficient_stats(off, dfn, ball, gamma)
        new_w, new_var = m_step(stats, weights, fit_weights)
        done = (abs(new_var - var) <= EM_TOL * var
                and max(abs(a - b) for a, b in zip(new_w, weights, strict=True)) <= EM_TOL)
        weights, var = new_w, new_var
    return weights, var, it


# --------------------------------------------------------------------------- the frames


def segment_starts(run_id: np.ndarray) -> np.ndarray:
    starts = np.ones(len(run_id), bool)
    starts[1:] = run_id[1:] != run_id[:-1]
    return starts


def arrays(frames: GameFrames, rows: np.ndarray | slice = slice(None)) -> tuple:
    xy = frames.xy[rows].astype(np.float64)
    return xy[:, :N_SIDE], xy[:, N_SIDE:], frames.ball[rows, :2].astype(np.float64)


def runs_of(frames: GameFrames) -> np.ndarray:
    return velocity_runs(frames.frame_idx, frames.possession_idx, frames.off_ids, frames.def_ids)


def halfcourt_data(frames: GameFrames) -> tuple:
    """The fit's input: the half-court rows, a new segment at every run change or gap."""
    run = runs_of(frames)
    keep = np.flatnonzero((frames.xy[:, :, 0] < 0).all(axis=1))
    starts = np.ones(len(keep), bool)
    starts[1:] = (run[keep[1:]] != run[keep[:-1]]) | (keep[1:] != keep[:-1] + 1)
    return (*arrays(frames, keep), starts)


def label_game(frames: GameFrames, weights, var: float, stay: float) -> dict:
    """Causal labels and filtered posteriors on every row, and the whole-segment path."""
    starts = segment_starts(runs_of(frames))
    ll = emission_loglik(*arrays(frames), weights, var)
    scores, back = viterbi_scores(ll, starts, stay)
    return {"causal": scores.argmax(axis=-1).astype(np.int8),
            "filtered": forward_filter(ll, starts, stay),
            "path": viterbi_paths(scores, back, starts)}


def frame_agreement(frames: GameFrames, lab: dict) -> np.ndarray:
    """Half-court defender-frames with a provider man: counts of (n, path, causal, nearest)."""
    half = (frames.xy[:, :, 0] < 0).all(axis=1)
    men = frames.matchup[:, None, :] == np.arange(N_SIDE)[None, :, None]  # (T, J, K)
    has = men.any(axis=-1) & half[:, None]
    d = np.linalg.norm(frames.xy[:, N_SIDE:, None, :] - frames.xy[:, None, :N_SIDE, :], axis=-1)
    t, j = np.nonzero(has)
    return np.array([len(t), men[t, j, lab["path"][t, j]].sum(),
                     men[t, j, lab["causal"][t, j]].sum(), men[t, j, d.argmin(-1)[t, j]].sum()])


def drive_labels(frames: GameFrames, kinds: pd.DataFrame, labs: dict[str, dict]) -> list[dict]:
    """One row per near-ok drive: the provider's man, the HMM's labels at r0, the baselines."""
    run = runs_of(frames)
    first = np.r_[0, np.flatnonzero(np.diff(run)) + 1]
    xy = frames.xy.astype(np.float64)
    rows = []
    for d in kinds[kinds["near_status"] == "ok"].itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        j, man = int(d.near_slot), int(d.near_man)
        pre = r0 - PRE_FRAMES
        pre_ok = pre >= 0 and run[pre] == run[r0]
        to_man = np.linalg.norm(xy[r0, N_SIDE:] - xy[r0, man], axis=1)
        to_att = np.linalg.norm(xy[r0, :N_SIDE] - xy[r0, N_SIDE + j], axis=1)
        row = {"drive_id": d.drive_id, "game": int(d.game), "start_frame": int(d.start_frame),
               "committed": bool(d.near_committed), "reference": bool(d.near_ref),
               "helper_slot": j, "handler_slot": int(d.handler_slot), "provider_man": man,
               "history_frames": int(r0 - first[run[r0]]),
               "r0_halfcourt": bool((xy[r0, :, 0] < 0).all()),
               "closest_attacker": int(to_att.argmin()),
               "coherent": int(to_man.argmin()) == j}
        for name, lab in labs.items():
            sfx = "" if name == "frozen" else f"_{name}"
            row[f"hmm_man{sfx}"] = int(lab["causal"][r0, j])
            row[f"post_provider{sfx}"] = float(lab["filtered"][r0, j, man])
            row[f"post_max{sfx}"] = float(lab["filtered"][r0, j].max())
        row["hmm_man_pre"] = int(labs["frozen"]["causal"][pre, j]) if pre_ok else -1
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- the answers


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson 95 % interval of a share k / n."""
    if n == 0:
        return np.nan, np.nan
    p, z2 = k / n, Z95**2
    den = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return centre - half, centre + half


def share_row(section: str, config: str, group: str, series: str, mask: pd.Series,
              note: str = "") -> dict:
    n, k = int(len(mask)), int(mask.sum())
    low, high = wilson(k, n)
    return {"section": section, "config": config, "group": group, "series": series, "n": n,
            "k": k, "value": k / n if n else np.nan, "ci_low": low, "ci_high": high,
            "note": note}


def groups_of(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"committed": df[df["committed"]], "reference": df[df["reference"]],
            "all_near_ok": df}


def headline_rows(config: str, keep: set, pairs: pd.DataFrame, out: pd.DataFrame) -> list[dict]:
    """The committed own mean, the reference's and the contrast, on the drives in `keep`."""
    p, d = pairs[pairs["drive_id"].isin(keep)], out[out["drive_id"].isin(keep)]
    rows = []
    for h in ROTATION_HORIZONS:
        for helped, group in ((True, "committed"), (False, "reference")):
            s = summarise(p, d, h, helped, HELP_FT)
            row = {"section": "headline", "config": config, "group": group,
                   "horizon": h / FPS, "series": "paired_diff", "n": s["n_drives"],
                   "value": s["mean_diff"], "ci_low": s["ci_low"], "ci_high": s["ci_high"]}
            if helped and h == HEADLINE_HORIZON:
                row["reading"] = reading(row["n"], row["ci_low"], row["ci_high"])
            rows.append(row)
        c = contrast(p, h)
        rows.append({"section": "headline", "config": config, "group": "contrast",
                     "horizon": h / FPS, "series": "contrast", "n": c["n_helped"],
                     "k": c["n_no_helper"], "value": c["contrast_mean"],
                     "ci_low": c["contrast_ci_low"], "ci_high": c["contrast_ci_high"],
                     "note": "k is the reference's n"})
    return rows


def assert_full_is_published(rows: list[dict], summary: pd.DataFrame) -> None:
    """The unrestricted re-run must equal help_kinds_summary.csv's near_committed rows."""
    for r in rows:
        kind = CLAIM + ("_ref" if r["group"] == "reference" else "")
        measure = "contrast" if r["group"] == "contrast" else "paired_diff"
        want = summary[(summary["measure"] == measure) & (summary["kind"] == kind)
                       & np.isclose(summary["horizon"], r["horizon"])]
        assert len(want) == 1, (measure, kind, r["horizon"])
        w = want.iloc[0]
        assert int(w["n"]) == int(r["n"]), (kind, r["horizon"])
        for got, col in ((r["value"], "mean"), (r["ci_low"], "ci_low"), (r["ci_high"], "ci_high")):
            assert abs(got - w[col]) < 1e-9, (kind, r["horizon"], col)


def assert_coherence_is_published(df: pd.DataFrame, coherence: pd.DataFrame) -> None:
    """The closest-defender baseline recomputed here must equal near_matchup_coherence.csv."""
    for name, g in groups_of(df).items():
        want = coherence.set_index("group").loc[name]
        assert (len(g), int(g["coherent"].sum())) == (int(want["n"]), int(want["n_coherent"])), name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    print(f"script sha256 {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]}")
    published = pd.read_csv(args.out / "help_kinds_summary.csv")
    coherence = pd.read_csv(args.out / "near_matchup_coherence.csv")

    dataset = Dataset(args.root)
    games = {g: get_or_build(dataset, g, args.cache) for g in dataset.game_ids}
    fit_data = [halfcourt_data(f) for f in games.values()]
    n_fit = sum(len(x[3]) for x in fit_data)
    _, var, it = fit_em(fit_data, STAY)
    w_fit, var_fit, it_fit = fit_em(fit_data, STAY, fit_weights=True)
    print(f"EM on {n_fit} half-court frames: sigma {math.sqrt(var):.3f} ft ({it} iterations); "
          f"weights fitted {w_fit[0]:.3f} / {w_fit[1]:.3f} / {w_fit[2]:.3f}, "
          f"sigma {math.sqrt(var_fit):.3f} ft ({it_fit} iterations)")
    configs = {"frozen": (WEIGHTS, var, STAY),
               **{f"stay_{s:.2f}": (WEIGHTS, var, s) for s in STAY_SENSITIVITY},
               "fitted_weights": (w_fit, var_fit, STAY)}

    rows, all_pairs, all_out, counts = [], [], [], {name: np.zeros(4) for name in configs}
    for g, frames in games.items():
        drives = dataset.events(g)["drives"]
        table = help_table(frames, drives)
        kinds = drive_kinds(frames, drives, table)
        t = kind_help_table(frames, table, kinds, CLAIM, "near_ref", "near")
        pairs, out = rotation_table(frames, drives, t)
        all_pairs.append(pairs)
        all_out.append(out)
        labs = {name: label_game(frames, *cfg) for name, cfg in configs.items()}
        for name, lab in labs.items():
            counts[name] += frame_agreement(frames, lab)
        rows += drive_labels(frames, kinds, labs)
    df = pd.DataFrame(rows)
    pairs = pd.concat(all_pairs, ignore_index=True)
    out = pd.concat(all_out, ignore_index=True)
    assert_coherence_is_published(df, coherence)

    summary = [{"section": "fit", "config": "frozen", "series": "sigma_ft", "n": n_fit,
                "value": math.sqrt(var), "note": f"weights {WEIGHTS}, stay {STAY}, {it} it"},
               {"section": "fit", "config": "fitted_weights", "series": "sigma_ft", "n": n_fit,
                "value": math.sqrt(var_fit), "note": f"{it_fit} it"}]
    summary += [{"section": "fit", "config": "fitted_weights", "series": f"w_{name}",
                 "n": n_fit, "value": w} for name, w in zip(("attacker", "ball", "hoop"), w_fit,
                                                            strict=True)]
    for name, (n, path, causal, nearest) in counts.items():
        for series, k in (("path", path), ("causal", causal), ("nearest_attacker", nearest)):
            low, high = wilson(int(k), int(n))
            summary.append({"section": "frames", "config": name, "group": "halfcourt",
                            "series": series, "n": int(n), "k": int(k), "value": k / n,
                            "ci_low": low, "ci_high": high,
                            "note": "defender-frames with a provider man"})

    sfx = {name: "" if name == "frozen" else f"_{name}" for name in configs}
    for group, g in groups_of(df).items():
        for name in configs:
            agree = g[f"hmm_man{sfx[name]}"] == g["provider_man"]
            summary.append(share_row("agreement", name, group, "hmm", agree))
            post = g[f"post_provider{sfx[name]}"]
            summary.append(share_row("ambiguous", name, group, "post_below_0.5",
                                     post < AMBIGUOUS_BELOW))
            summary.append(share_row("ambiguous", name, group, "post_below_0.9",
                                     post < CONFIDENT_FROM, "reported, not read"))
        summary.append({"section": "agreement", "config": "baseline", "group": group,
                        "series": "chance", "n": len(g), "value": CHANCE})
        summary.append(share_row("agreement", "baseline", group, "closest_defender",
                                 g["coherent"], "near_matchup_coherence.csv"))
        summary.append(share_row("agreement", "baseline", group, "closest_attacker",
                                 g["closest_attacker"] == g["provider_man"]))
        pre = g[g["hmm_man_pre"] >= 0]
        summary.append(share_row("agreement", "frozen", group, "hmm_1s_before",
                                 pre["hmm_man_pre"] == pre["provider_man"],
                                 "label 1.0 s before r0, same segment"))
        miss = g[g["hmm_man"] != g["provider_man"]]
        summary.append(share_row("agreement", "frozen", group, "disagree_on_handler",
                                 miss["hmm_man"] == miss["handler_slot"],
                                 "of the disagreements: the HMM places him with the handler"))

    full = headline_rows("all", set(df["drive_id"]), pairs, out)
    assert_full_is_published(full, published)
    summary += full
    for name in configs:
        keep = set(df.loc[df[f"hmm_man{sfx[name]}"] == df["provider_man"], "drive_id"])
        summary += headline_rows(f"agree_{name}", keep, pairs, out)

    df.to_csv(args.out / "hmm_matchups.csv", index=False)
    table = pd.DataFrame(summary).reindex(columns=["section", "config", "group", "horizon",
                                                   "series", "n", "k", "value", "ci_low",
                                                   "ci_high", "reading", "note"])
    table.to_csv(args.out / "hmm_matchups_summary.csv", index=False)
    print("unrestricted re-run equals help_kinds_summary.csv; closest-defender baseline equals "
          "near_matchup_coherence.csv")
    with pd.option_context("display.width", 220, "display.max_rows", 500,
                           "display.float_format", "{:.3f}".format):
        print(table.drop(columns=["note"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
