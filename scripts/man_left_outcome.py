"""What happens to the man the helper left: the ball, his clearance at the catch, the shot (14.f 2).

Usage: uv run python scripts/man_left_outcome.py [--root DIR] [--cache DIR] [--out DIR]

The entry shows that after a committed near help nobody moves toward the man left more than
toward any other attacker; it never shows what that costs. This script reads, on the same
drives, three outcomes of that man, against a reference. Displacements and distances only: a
pass "reaches" him, he "takes" a shot; nothing here says anyone chose anything.

Groups (read from `scbasket.help_kinds.drive_kinds` unchanged, so the split is the headline's;
counts asserted equal to `help_kinds_summary.csv`):

- **committed**: `near_committed` (the nearest off-ball defender steps >= 2 ft toward the
  handler within 1.0 s and at 2.0 s stands > 1 ft farther from where his man started).
- **recovered**: `near_stunt` (the same step, back within 1 ft at 2.0 s); only in the step split.
- **reference**: `near_ref` (the nearest moves < 1 ft toward the handler), the README's "the
  reference". In all three, "the man" is the nearest's RAW provider man at the drive's start,
  exactly as `kind_help_table` names the man left for the headline and its contrast.

Why this reference and not the headline's placebo (the other attackers of the same drive): the
placebo compares one defender's movement toward different targets at the same moment; an
outcome compares ATTACKERS, and the man left is by construction the man of the off-ball
defender nearest the ball, so his role alone could make the ball find him more often. The
stays-home drives hold that role fixed and differ only in the helper's movement (the split of
the contrast row). The placebo comparison (the man against the other off-ball attackers, the
handler excluded) is still written, in both groups, so a role effect can be seen for what it is.

Frozen in this header on 2026-10-31 before the first run. NOT a pre-registration: the entry's
own numbers (and that the committed drives have more passes in the first 1.52 s, 28 of 246
against 4 of 199, `near_pass.csv`) were seen before these windows were written.

- **The window.** A complete pass to the attacker, in the drive's chance, RELEASED in
  (start + 2.0 s, start + 5.0 s]. It opens at 2.0 s because the split reads the helper's
  position until then (`help_kinds.OUTCOME_FRAMES`): a pass to his man before 2.0 s can pull
  him back and turn a committed help into a stunt, so a window from the step would let the
  outcome choose the group (the lesson "a check that cannot fail"). The reference has no step,
  so both groups are anchored on the drive's start. The 3.0 s length is ours. Sensitivity
  `from_start`: released in (start, start + 5.0 s], reported because it is what a naive reading
  would use, and flagged: the split can read it.
- **Reached.** At least one such pass (per drive; per attacker-drive for the placebo).
- **Clearance at the catch.** At the first such pass's `endFrame`, the receiver's distance to
  the nearest defender (feet, tracked positions). **Open at the catch**: clearance >= OPEN_FT,
  6 ft, the threshold Lucey et al. 2014 use for an open shot AT THE RELEASE (read from the
  Disney Research summary, not the PDF; `docs/research/help_defense_literature.md`); applying it
  at the catch is ours. Chang et al. 2014 was not opened: no threshold comes from it.
- **Shot.** A shot by the receiver (the provider's `shots`, fouled ones included: a shot
  taken) in the same chance, starting within SHOT_FRAMES (2.0 s, ours) of that catch.
  `shot_per_catch` among the drives where he caught; `shot_per_drive` over all drives.
- **Catch check.** The event catch against the tracking: the tracked ball's distance to the
  receiver at the pass's release and at its `endFrame` (the ball must arrive at him). Changed
  after the first run: the frozen check, the ball within HOLDER_MAX_DIST_FT (3 ft) of him at
  `endFrame`, read 25 to 42 % and was RETIRED, not adjusted: on the 198 catches of the first
  run the ball closes from a median 16.9 ft 0.6 s before `endFrame` to 3.7 ft at it and 1.6 ft
  0.2 s after, so the event is aligned and 3 ft at the body point was the wrong yardstick
  (scratchpad `catch_check.py`, not shipped).
- **Intervals.** 95 % percentile bootstrap, BOOTSTRAP_DRAWS and BOOTSTRAP_SEED of
  `second_help`. Primary: resampling GAMES (ten: few clusters, intervals likely too narrow);
  the difference is also given resampling drives (`*_drive`). Each comparison resamples only
  the drives of its own population.

The step split, added 2026-10-31 after the first results were read (the lead's follow-up) and
frozen here before its own run; NOT a pre-registration either:

- **Near help** = committed + recovered: the step classifier alone (the nearest moves >=
  NEAR_STEP_FT toward the handler within 1.0 s), before the 2.0 s rule. Against the same
  stays-home reference.
- **The step window** (`step`): a complete pass to the attacker released from the step frame
  to STEP_WINDOW_FRAMES (3.0 s, ours) after it. The step frame is the FIRST frame in 1..1.0 s
  at which the nearest's projection toward the handler (`near_move`'s projection) reaches
  NEAR_STEP_FT: the flag is fixed at that frame, so nothing inside the window can move a drive
  into or out of near help. A stays-home drive has no step; its window opens at the median
  step frame of its own game's near-help drives (rounded down). The reference flag reads the
  whole first 1.0 s, so a pass to the man between that frame and 1.0 s could keep his defender
  home: those reference drives are counted (`leak`), not removed.
- **Early pass** (`early`): a complete pass to the attacker released in (start, start + 2.0 s],
  counted per group to size the selection the committed rule makes.

Writes to {out}:
  man_left_outcome.csv          one row per (drive, off-ball attacker): group, role (man |
                                placebo), the step frame (s), and per window the release /
                                catch delay (s from the drive's start), clearance, open, shot,
                                ball distance at release and at catch
  man_left_outcome_summary.csv  comparison x window x quantity: n, mean and game CI of a and b,
                                a - b with its game and drive CIs
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from second_help import BOOTSTRAP_DRAWS, BOOTSTRAP_SEED

from scbasket.frames import N_SIDE, get_or_build
from scbasket.help_kinds import MOVE_FRAMES, NEAR_STEP_FT, OUTCOME_FRAMES, drive_kinds
from scbasket.io import Dataset
from scbasket.rotation import _projection
from scbasket.wind import FPS, OPEN_FT, _row_of, help_table

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

#: Release windows, frames after the drive's start, (lo, hi]: frozen before the first run.
WINDOWS = {"primary": (OUTCOME_FRAMES, 125), "from_start": (0, 125)}
#: The step window runs this many frames from the step frame (3.0 s, ours).
STEP_WINDOW_FRAMES = 75
#: A shot counts if it starts within this many frames of the catch (2.0 s, ours).
SHOT_FRAMES = 50
FIXED = tuple(WINDOWS)
OLD = ("committed", "reference")
#: comparison -> (windows, population groups, (groups, role) of a, (groups, role) of b).
COMPARISONS = {
    "committed_vs_reference": (FIXED, OLD, (("committed",), "man"), (("reference",), "man")),
    "man_vs_placebo_committed": (FIXED, OLD, (("committed",), "man"),
                                 (("committed",), "placebo")),
    "man_vs_placebo_reference": (FIXED, OLD, (("reference",), "man"),
                                 (("reference",), "placebo")),
    "help_vs_reference": (("step",), ("committed", "recovered", "reference"),
                          (("committed", "recovered"), "man"), (("reference",), "man")),
}
#: quantity -> column prefix in the per-row table.
QUANTITIES = {"reached": "reached", "clear_catch": "clear", "open_catch": "open",
              "shot_per_catch": "shot", "shot_per_drive": "shot_any",
              "ball_ft_release": "ball_release", "ball_ft_catch": "ball_catch"}
NOTE = ("Windows and thresholds frozen in the script header before each split's first run; "
        "NOT a pre-registration (the entry's own numbers were seen first).")


def first_catch(passes: pd.DataFrame, chance_id, receiver_id: int, start_frame: int,
                window: tuple[int, int]) -> tuple[int, int] | None:
    """(release, catch) frames of the first complete pass to `receiver_id` in the chance whose
    release lies in (start_frame + lo, start_frame + hi], or None."""
    lo, hi = window
    p = passes[(passes["chanceId"] == chance_id) & (passes["receiverId"] == receiver_id)
               & passes["complete"].eq(True)
               & (passes["startFrame"] > start_frame + lo)
               & (passes["startFrame"] <= start_frame + hi)]
    if not len(p):
        return None
    first = p.sort_values("startFrame").iloc[0]
    return int(first["startFrame"]), int(first["endFrame"])


def shot_after(shots: pd.DataFrame, chance_id, shooter_id: int, catch: int) -> bool:
    """A shot by `shooter_id` in the chance starting within SHOT_FRAMES of the catch."""
    s = shots[(shots["chanceId"] == chance_id) & (shots["shooterId"] == shooter_id)
              & (shots["startFrame"] >= catch) & (shots["startFrame"] <= catch + SHOT_FRAMES)]
    return len(s) > 0


def at_frame(frames, frame: int, player_id: int) -> tuple[float, float]:
    """The player's clearance (feet to the nearest defender) and the tracked ball's distance to
    him at `frame`; NaN when the cache lacks the frame or the player."""
    r = _row_of(frames.frame_idx, frame)
    if r < 0:
        return np.nan, np.nan
    slot = np.flatnonzero(frames.off_ids[r] == player_id)
    if not len(slot):
        return np.nan, np.nan
    xy = frames.xy[r].astype(np.float64)
    me = xy[int(slot[0])]
    return (float(np.linalg.norm(xy[N_SIDE:] - me, axis=1).min()),
            float(np.linalg.norm(frames.ball[r, :2].astype(np.float64) - me)))


def step_frame(xy: np.ndarray, r0: int, near: int, handler: int) -> int:
    """The first frame t in 1..MOVE_FRAMES at which the nearest defender's displacement,
    projected toward the handler where he is at t, reaches NEAR_STEP_FT; -1 if never."""
    for t in range(1, MOVE_FRAMES + 1):
        if _projection(xy[r0, N_SIDE + near], xy[r0 + t, N_SIDE + near],
                       xy[r0 + t, handler]) >= NEAR_STEP_FT:
            return t
    return -1


def catch_values(frames, passes, shots, chance, pid: int, start: int,
                 window: tuple[int, int]) -> dict:
    """Reached, release / catch delay, clearance, open, shot and ball distances in one window."""
    got = first_catch(passes, chance, pid, start, window)
    vals = {"reached": float(got is not None), "release_s": np.nan, "catch_s": np.nan,
            "clear": np.nan, "open": np.nan, "shot": np.nan, "shot_any": 0.0,
            "ball_release": np.nan, "ball_catch": np.nan}
    if got is not None:
        release, catch = got
        clear, ball_catch = at_frame(frames, catch, pid)
        shot = float(shot_after(shots, chance, pid, catch))
        vals.update({"release_s": (release - start) / FPS, "catch_s": (catch - start) / FPS,
                     "clear": clear,
                     "open": float(clear >= OPEN_FT) if np.isfinite(clear) else np.nan,
                     "shot": shot, "shot_any": shot,
                     "ball_release": at_frame(frames, release, pid)[1],
                     "ball_catch": ball_catch})
    return vals


def outcome_rows(frames, events: dict, kinds: pd.DataFrame) -> list[dict]:
    """One row per (committed, recovered or reference drive, off-ball attacker at the start)."""
    drives, passes, shots = events["drives"], events["passes"], events["shots"]
    chance_of = dict(zip(drives["id"], drives["chanceId"], strict=True))
    xy = frames.xy.astype(np.float64)
    use = kinds[kinds["near_committed"] | kinds["near_stunt"] | kinds["near_ref"]]
    steps = {}
    for d in use[~use["near_ref"]].itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        steps[d.drive_id] = step_frame(xy, r0, int(d.near_slot), int(d.handler_slot))
        assert steps[d.drive_id] > 0, d.drive_id  # the flag says he reached NEAR_STEP_FT
    matched = int(np.median(list(steps.values()))) if steps else -1
    rows = []
    for d in use.itertuples(index=False):
        r0 = _row_of(frames.frame_idx, int(d.start_frame))
        chance, start = chance_of[d.drive_id], int(d.start_frame)
        step = steps.get(d.drive_id, matched)
        assert step > 0, d.drive_id
        windows = {**WINDOWS, "step": (step - 1, step + STEP_WINDOW_FRAMES),
                   "early": (0, OUTCOME_FRAMES)}
        for a in range(N_SIDE):
            if a == int(d.handler_slot):
                continue
            pid = int(frames.off_ids[r0, a])
            row = {"drive_id": d.drive_id, "game": int(d.game),
                   "group": ("committed" if d.near_committed
                             else "recovered" if d.near_stunt else "reference"),
                   "role": "man" if a == int(d.near_man) else "placebo", "attacker_id": pid,
                   "step_s": step / FPS, "step_matched": bool(d.near_ref)}
            for name, window in windows.items():
                vals = catch_values(frames, passes, shots, chance, pid, start, window)
                row.update({f"{k}_{name}": v for k, v in vals.items()})
            rows.append(row)
    return rows


def cluster_ci(values: np.ndarray, clusters: np.ndarray, in_a: np.ndarray,
               in_b: np.ndarray) -> dict:
    """Means of a, b and a - b with 95 % percentile intervals from resampling clusters with
    replacement (BOOTSTRAP_DRAWS, BOOTSTRAP_SEED); NaN values are left out of every mean."""
    ok = ~np.isnan(values)
    ids, inv = np.unique(clusters, return_inverse=True)

    def sums(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        m = mask & ok
        return (np.bincount(inv, weights=np.where(m, values, 0.0), minlength=len(ids)),
                np.bincount(inv, weights=m.astype(float), minlength=len(ids)))

    (sa, ca), (sb, cb) = sums(in_a), sums(in_b)
    pick = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, len(ids), size=(BOOTSTRAP_DRAWS, len(ids)))
    with np.errstate(invalid="ignore", divide="ignore"):
        ma, mb = sa[pick].sum(1) / ca[pick].sum(1), sb[pick].sum(1) / cb[pick].sum(1)
        mean_a, mean_b = sa.sum() / ca.sum(), sb.sum() / cb.sum()
    out = {"n_a": int(ca.sum()), "mean_a": float(mean_a), "n_b": int(cb.sum()),
           "mean_b": float(mean_b), "diff": float(mean_a - mean_b)}
    for key, draws in (("a", ma), ("b", mb), ("diff", ma - mb)):
        finite = draws[np.isfinite(draws)]
        low, high = np.percentile(finite, [2.5, 97.5]) if len(finite) else (np.nan, np.nan)
        out[f"ci_low_{key}"], out[f"ci_high_{key}"] = float(low), float(high)
    return out


def summarise(rows: pd.DataFrame) -> pd.DataFrame:
    """Every comparison x window x quantity, by game and (the difference) by drive."""
    out = []
    for comp, (windows, population, (ga, ra), (gb, rb)) in COMPARISONS.items():
        pop = rows[rows["group"].isin(population)]
        in_a = (pop["group"].isin(ga) & (pop["role"] == ra)).to_numpy()
        in_b = (pop["group"].isin(gb) & (pop["role"] == rb)).to_numpy()
        for window in windows:
            for quantity, prefix in QUANTITIES.items():
                v = pop[f"{prefix}_{window}"].to_numpy(dtype=np.float64)
                games = cluster_ci(v, pop["game"].to_numpy(), in_a, in_b)
                by_drive = cluster_ci(v, pop["drive_id"].to_numpy(), in_a, in_b)
                out.append({"comparison": comp, "window": window, "quantity": quantity,
                            "a": f"{'+'.join(ga)}_{ra}", "b": f"{'+'.join(gb)}_{rb}", **games,
                            "ci_low_diff_drive": by_drive["ci_low_diff"],
                            "ci_high_diff_drive": by_drive["ci_high_diff"]})
    return pd.DataFrame(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=DATA)
    parser.add_argument("--cache", type=Path, default=INTERIM)
    parser.add_argument("--out", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    dataset = Dataset(args.root)
    rows = []
    for game in dataset.game_ids:
        frames = get_or_build(dataset, game, args.cache)
        events = dataset.events(game)
        kinds = drive_kinds(frames, events["drives"], help_table(frames, events["drives"]))
        rows += outcome_rows(frames, events, kinds)
    rows = pd.DataFrame(rows)

    # The split is the headline's: same drive counts as help_kinds_summary.csv.
    men = rows[rows["role"] == "man"]
    by_group = men["group"].value_counts()
    counts = pd.read_csv(args.out / "help_kinds_summary.csv")
    counts = counts[(counts["measure"] == "count") & (counts["kind"] == "flag")]
    want = dict(zip(counts["variant"], counts["n"], strict=True))
    for group, flag in (("committed", "near_committed"), ("recovered", "near_stunt"),
                        ("reference", "near_ref")):
        assert by_group.get(group, 0) == want[flag], (group, by_group, want)
    assert (rows.groupby("drive_id")["role"].apply(lambda r: (r == "man").sum()) == 1).all()

    rows.to_csv(args.out / "man_left_outcome.csv", index=False)
    summary = summarise(rows)
    summary.to_csv(args.out / "man_left_outcome_summary.csv", index=False)

    print(NOTE)
    print(f"drives: committed {by_group['committed']}, recovered {by_group['recovered']}, "
          f"reference {by_group['reference']}; window primary (start + "
          f"{WINDOWS['primary'][0] / FPS:.1f} s, start + {WINDOWS['primary'][1] / FPS:.1f} s], "
          f"step window [step, step + {STEP_WINDOW_FRAMES / FPS:.1f} s], open >= "
          f"{OPEN_FT:.0f} ft, shot within {SHOT_FRAMES / FPS:.1f} s of the catch; CIs resample "
          f"games ({rows['game'].nunique()})")
    print("\nthe man: a complete pass to him released in the first "
          f"{OUTCOME_FRAMES / FPS:.1f} s (early), by group")
    print(men.groupby("group")["reached_early"].agg(["sum", "count", "mean"]).to_string())
    print("\nstep frame (s): near help median "
          f"{men.loc[~men['step_matched'], 'step_s'].median():.2f}; matched frames per game "
          f"{sorted(men.loc[men['step_matched'], 'step_s'].unique().round(2).tolist())}")
    ref = men[men["step_matched"] & (men["reached_step"] == 1)]
    leak = int((ref["release_s_step"] <= MOVE_FRAMES / FPS).sum())
    print(f"leak: reference drives whose step-window pass to the man is released by "
          f"{MOVE_FRAMES / FPS:.1f} s (the reference flag reads it): {leak} of {len(ref)}")
    cols = ["window", "quantity", "n_a", "mean_a", "ci_low_a", "ci_high_a", "n_b", "mean_b",
            "ci_low_b", "ci_high_b", "diff", "ci_low_diff", "ci_high_diff",
            "ci_low_diff_drive", "ci_high_diff_drive"]
    with pd.option_context("display.width", 250, "display.max_columns", 30,
                           "display.float_format", "{:.3f}".format):
        for comp, g in summary.groupby("comparison", sort=False):
            print(f"\n{comp}: a = {g['a'].iloc[0]}, b = {g['b'].iloc[0]}")
            print(g[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
