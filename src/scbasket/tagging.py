"""The high-side layer: tag geometry at the shot, and what the opponent does next (F5).

SkillCorner's open bundle carries no crash, box-out or retreat label (confirmed with them
on 2026-09-17), so this module DERIVES the layer from tracking. It is published as a
DEFINITION, never as a detector: it does not claim to read whether a player intended to
tag, it measures a stated geometric quantity, exactly as `closestDefDist` measures a
distance without claiming to know why the defender stood there.

``tag_features`` describes where the non-shooting attackers stand relative to their own
defenders at the moment of a missed shot. ``transition_outcome`` describes what the
rebounding team then does with the possession it just won.

The trap this module is built around: sitting on the high side correlates mechanically
with standing deep, and standing deep costs offensive rebounds. So ``tag_features`` also
returns the DEPTH CONTROLS, and F5 grades every criterion against a baseline that already
contains them. If the tag geometry only restates how far back the attackers were, it must
fail, and showing that is the deliverable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scbasket.control import ControlParams, control_field
from scbasket.court import HOOP_X, Grid
from scbasket.forward import MIN_POINTS
from scbasket.frames import N_SIDE, GameFrames, at_frames, matchup_with_fallback
from scbasket.value import ValueSurface

FPS = 25
TRANSITION_WINDOW_S = 4.0
TRANSITION_WINDOW_FRAMES = int(TRANSITION_WINDOW_S * FPS)

#: The basket the attacking team is shooting at, and the one they must now defend. The
#: attacking frame puts the attacked hoop at (HOOP_X, 0) with the attack toward negative x.
ATTACKED_HOOP = np.array([HOOP_X, 0.0])
OWN_HOOP = np.array([-HOOP_X, 0.0])


def high_side_distance(frames: GameFrames) -> np.ndarray:
    """(N, 5) signed feet each attacker sits on the high side of their matched defender.

    Positive means the attacker is between that defender and the basket the attacker must
    now defend: the "high side" of the tag. The sign comes from projecting the attacker's
    offset from their defender onto the unit vector running from the defender toward
    ``OWN_HOOP``, so it is a distance along the retreat direction and not a raw separation.

    The matchup is ``matchup_with_fallback``, so a frame whose provider assignment is
    missing falls back to the nearest defender rather than dropping out.
    """
    xy = frames.xy.astype(np.float64)
    matchup = matchup_with_fallback(frames).astype(np.int64)
    defender_xy = np.take_along_axis(
        xy[:, N_SIDE:], matchup[:, :, None].repeat(2, axis=2), axis=1
    )
    toward_own = OWN_HOOP[None, None, :] - defender_xy
    norm = np.linalg.norm(toward_own, axis=-1, keepdims=True)
    toward_own = np.divide(toward_own, norm, out=np.zeros_like(toward_own), where=norm > 0)
    return ((xy[:, :N_SIDE] - defender_xy) * toward_own).sum(axis=-1)


def tag_features(release: GameFrames, shots: pd.DataFrame) -> pd.DataFrame:
    """One row per shot of `shots`, aligned to its already-matched release frame.

    `release` must be the frames at those shots' release, in the same order and of the same
    length (``scbasket.validation.match_shots_to_release`` produces exactly that pair).

    The shooter is excluded from every aggregate: they are not tagging anyone, they are
    shooting, and leaving them in would put a player who is by construction near the
    offensive rim into a measure of how the OTHER four positioned themselves.

    Columns split into two blocks that F5 keeps apart on purpose:
      - the tag geometry: `tag_index`, `high_side_mean`, `high_side_min`, `high_side_max`
      - the DEPTH CONTROLS: `off_rim_dist_mean`, `off_rim_dist_min`, `own_rim_dist_mean`,
        `n_inside_15ft`. Any criterion on the first block is graded against these.
    """
    if len(release) != len(shots):
        raise ValueError(f"release has {len(release)} frames, shots has {len(shots)} rows")
    if len(release) == 0:
        return pd.DataFrame(index=pd.RangeIndex(0), columns=_TAG_COLUMNS, dtype=float)

    high_side = high_side_distance(release)
    others = release.off_ids != shots["shooterId"].to_numpy()[:, None]
    if not others.any(axis=1).all():
        raise ValueError("a release frame has no non-shooting attacker; check the matching")

    xy = release.xy[:, :N_SIDE].astype(np.float64)
    off_rim = np.linalg.norm(xy - ATTACKED_HOOP[None, None, :], axis=-1)
    own_rim = np.linalg.norm(xy - OWN_HOOP[None, None, :], axis=-1)
    n_others = others.sum(axis=1)

    return pd.DataFrame(
        {
            "tag_index": ((high_side > 0) & others).sum(axis=1) / n_others,
            "high_side_mean": high_side.mean(axis=1, where=others),
            "high_side_min": high_side.min(axis=1, where=others, initial=np.inf),
            "high_side_max": high_side.max(axis=1, where=others, initial=-np.inf),
            "off_rim_dist_mean": off_rim.mean(axis=1, where=others),
            "off_rim_dist_min": off_rim.min(axis=1, where=others, initial=np.inf),
            "own_rim_dist_mean": own_rim.mean(axis=1, where=others),
            "n_inside_15ft": ((off_rim <= 15.0) & others).sum(axis=1),
        }
    )


_TAG_COLUMNS = (
    "tag_index", "high_side_mean", "high_side_min", "high_side_max",
    "off_rim_dist_mean", "off_rim_dist_min", "own_rim_dist_mean", "n_inside_15ft",
)

#: The block every tag criterion is graded against, so the geometry has to beat "they were
#: simply standing further back" rather than restate it.
DEPTH_CONTROLS = (
    "off_rim_dist_mean", "off_rim_dist_min", "own_rim_dist_mean", "n_inside_15ft",
)
TAG_FEATURES = ("tag_index", "high_side_mean", "high_side_min", "high_side_max")


def transition_outcome(
    frames: GameFrames,
    rebounds: pd.DataFrame,
    chances: pd.DataFrame,
    grid: Grid,
    params: ControlParams,
    surface: ValueSurface,
    *,
    window_frames: int = TRANSITION_WINDOW_FRAMES,
    min_points: float = MIN_POINTS,
) -> pd.DataFrame:
    """One row per DEFENSIVE rebound: what the team that won it did with the next chance.

    The headline outcome is `break_area`, the mean `area_valuable` of the rebounding team
    over the first `window_frames` of the chance they then start. The cached frames of that
    chance are already oriented to ITS attacking team (frames.py resolves orientation per
    possession), so the control field read there measures the space the BREAKING team owns:
    high `break_area` means the retreat failed. This is P1.8's instrument, whose criterion 2
    passed out of sample, pointed at a different question.

    `next_pts` and `next_transition` come from the events and are reported alongside, never
    instead: points on one chance are far noisier than the space measured over four seconds.
    Rows whose next chance has no cached frame get NaN in `break_area` and are counted, not
    dropped silently by the caller.
    """
    defensive = rebounds["defensive"].astype(bool)
    rows = rebounds[defensive & rebounds["nextChanceId"].notna()].reset_index(drop=True)
    chance_row = pd.Series(np.arange(len(chances)), index=chances["id"])
    next_idx = rows["nextChanceId"].map(chance_row).to_numpy(dtype=float)

    by_id = chances.set_index("id")
    out = pd.DataFrame(
        {
            "rebound_id": rows["id"],
            "shot_id": rows["shotId"],
            "next_chance_idx": next_idx,
            "next_transition": rows["nextChanceId"].map(by_id["transition"]).astype("boolean"),
            "next_pts": rows["nextChanceId"].map(by_id["ptsScored"]).astype(float),
            "break_area": np.nan,
        }
    )

    known = np.flatnonzero(~np.isnan(next_idx))
    for row in known:
        chance = int(next_idx[row])
        in_chance = np.flatnonzero(frames.chance_idx == chance)
        if in_chance.size == 0:
            continue
        window = frames.take(in_chance)
        start = window.frame_idx.min()
        window = window.take(window.frame_idx <= start + window_frames)
        p_off = control_field(window, grid, params)
        weighted = p_off * np.asarray(surface.values, dtype=np.float64)[None, :]
        area = (weighted >= min_points).sum(axis=1) * grid.cell_ft**2
        out.loc[row, "break_area"] = float(area.mean())
    return out


def release_frames_for(frames: GameFrames, shots: pd.DataFrame) -> tuple[GameFrames, pd.DataFrame]:
    """Missed shots whose release frame is cached, and those frames, aligned and in order.

    Kept here rather than reused from validation.match_shots_to_release because F5 needs the
    MISSED shots only and does not need the shooter's xy, and because the shooter-slot check
    there would drop a row this module can still describe.
    """
    missed = shots[(shots["outcome"] == False) & shots["startFrame"].notna()]  # noqa: E712
    wanted = missed["startFrame"].to_numpy(dtype=np.int64)
    release = at_frames(frames, wanted)
    matched = missed[missed["startFrame"].isin(release.frame_idx)].reset_index(drop=True)
    return release, matched
