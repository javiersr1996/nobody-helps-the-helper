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


# ------------------------------------------------------------------ construct validity (P5.1b)


def _xy_of_players(frame: GameFrames, ids: np.ndarray) -> np.ndarray:
    """(K, 2) position of each requested player id in a ONE-row GameFrames; NaN if absent.

    Possession flips between the shot and the break, so a player who was in ``off_ids`` at
    the release sits in ``def_ids`` afterwards. Everything here is keyed on the player id
    and never on the slot, which is what makes the pairing survive the flip.
    """
    all_ids = np.concatenate([frame.off_ids[0], frame.def_ids[0]])
    all_xy = frame.xy[0].astype(np.float64)
    out = np.full((len(ids), 2), np.nan)
    for k, pid in enumerate(ids):
        slot = np.flatnonzero(all_ids == pid)
        if slot.size:
            out[k] = all_xy[slot[0]]
    return out


def retreat_pairs(release: GameFrames, shots: pd.DataFrame) -> list[np.ndarray]:
    """Per shot, the (4, 2) array of (attacker id, their matched defender id) at the release.

    These are the pairs tagging up claims to preserve into the retreat: the attacker who
    tagged a defender should still be the one guarding them once the break arrives.
    """
    matchup = matchup_with_fallback(release).astype(np.int64)
    shooter = shots["shooterId"].to_numpy()
    pairs = []
    for i in range(len(release)):
        others = np.flatnonzero(release.off_ids[i] != shooter[i])
        pairs.append(
            np.column_stack([release.off_ids[i][others], release.def_ids[i][matchup[i][others]]])
        )
    return pairs


def retreat_match_distance(
    frames: GameFrames,
    release: GameFrames,
    shots: pd.DataFrame,
    rebounds: pd.DataFrame,
    chances: pd.DataFrame,
) -> pd.DataFrame:
    """Were the release-time pairs still together when the opponent reached the frontcourt?

    This is P5.1b's discriminating check, and it is what separates tagging up from simply
    retreating deep. Plain retreat puts you back in time; it does not put you back ATTACHED
    to the man you were next to. So for every missed shot the other team rebounded, the
    four release pairs are re-measured at that next chance's ``frontcourtFrame``.

    Columns: `match_dist` (mean feet between the four pairs there, NaN if the frame or a
    player is missing), `n_pairs_found`, and `secs_to_frontcourt` (rebound to frontcourt,
    the speed of the break the retreat was facing).

    It shares the matchup ASSIGNMENT with `tag_features` and nothing else: one is a signed
    projection at the release, the other a distance seconds later, and a player can be high
    side at the shot and 15 ft adrift by the time it matters.
    """
    by_shot = rebounds[rebounds["defensive"].astype(bool)].set_index("shotId")
    chance_row = pd.Series(np.arange(len(chances)), index=chances["id"])
    frontcourt = chances["frontcourtFrame"].to_numpy(dtype=float)
    pairs = retreat_pairs(release, shots)

    rows = []
    for i, shot_id in enumerate(shots["id"].to_numpy()):
        row = {"match_dist": np.nan, "n_pairs_found": 0, "secs_to_frontcourt": np.nan}
        if shot_id in by_shot.index:
            rebound = by_shot.loc[shot_id]
            rebound = rebound.iloc[0] if isinstance(rebound, pd.DataFrame) else rebound
            chance = chance_row.get(rebound["nextChanceId"], np.nan)
            if not np.isnan(chance) and not np.isnan(frontcourt[int(chance)]):
                target = int(frontcourt[int(chance)])
                at = at_frames(frames, np.array([target]))
                if len(at):
                    xy = _xy_of_players(at, pairs[i].ravel()).reshape(-1, 2, 2)
                    dist = np.linalg.norm(xy[:, 0] - xy[:, 1], axis=-1)
                    found = np.isfinite(dist)
                    row["n_pairs_found"] = int(found.sum())
                    if found.any():
                        row["match_dist"] = float(dist[found].mean())
                    row["secs_to_frontcourt"] = (target - float(rebound["frame"])) / FPS
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------- the flight re-specification (P5.1c)

MAX_FLIGHT_S = 2.0
MAX_FLIGHT_FRAMES = int(MAX_FLIGHT_S * FPS)


def high_side_for_pairs(frame: GameFrames, pairs: np.ndarray) -> np.ndarray:
    """(K,) signed high side for explicit (attacker id, defender id) pairs in a ONE-row frame.

    Keyed on ids, so the SAME pairing can be evaluated at two instants even though slots and
    possession may have moved in between. NaN where either player is absent from the frame.
    """
    xy = _xy_of_players(frame, pairs.ravel()).reshape(-1, 2, 2)
    attacker, defender = xy[:, 0], xy[:, 1]
    toward_own = OWN_HOOP[None, :] - defender
    norm = np.linalg.norm(toward_own, axis=-1, keepdims=True)
    toward_own = np.divide(toward_own, norm, out=np.zeros_like(toward_own), where=norm > 0)
    return ((attacker - defender) * toward_own).sum(axis=-1)


def tag_flight_features(
    frames: GameFrames,
    release: GameFrames,
    shots: pd.DataFrame,
    rebounds: pd.DataFrame,
    *,
    max_flight_frames: int = MAX_FLIGHT_FRAMES,
) -> pd.DataFrame:
    """P5.1c: the tag measured as a MOVEMENT over the shot flight, not a pose at the release.

    P5.1b failed because P5.1 measured the wrong instant. Tagging up is executed while the
    ball is in the air: the attackers run AT their defenders after the shot leaves. The
    release frame is the state before that, so it described the offensive shape the
    possession ended in and not the tag.

    Here the pairs are fixed at the release and then re-measured at the moment the ball is
    rebounded (capped at `max_flight_frames` after the release, and skipped when no rebound
    frame exists). `high_side_gain` is the difference: how much high side each attacker
    actually TOOK during the flight. A gain is immune by construction to the depth confound
    that swallowed P5.1b, because a player who was already deep and stayed there gains zero.

    One window, taken from the mechanism, and P5.1c is the only retry F5 allows itself.
    Trying windows until one passes is the failure this project has been punished for twice.

    Noted rather than buried: at the rebound frame the ball is being secured, so the END
    level partly reflects who won it. That is harmless for the P5.1b check, whose outcome is
    measured seconds later at the opponent's frontcourt crossing, but any use of these
    columns against a rebound outcome has to reckon with it.
    """
    pairs = retreat_pairs(release, shots)
    by_shot = rebounds.set_index("shotId")["frame"]
    by_shot = by_shot[~by_shot.index.duplicated()]
    rows = []
    for i, shot_id in enumerate(shots["id"].to_numpy()):
        start = int(release.frame_idx[i])
        at_start = high_side_for_pairs(release.take(np.array([i])), pairs[i])
        row = {
            "high_side_gain_mean": np.nan, "high_side_gain_min": np.nan,
            "tag_index_end": np.nan, "high_side_end_mean": np.nan,
            "flight_secs": np.nan, "n_flight_pairs": 0,
        }
        end_frame = by_shot.get(shot_id, np.nan)
        if np.isfinite(end_frame):
            target = min(int(end_frame), start + max_flight_frames)
            at = at_frames(frames, np.array([target]))
            if len(at) and target > start:
                at_end = high_side_for_pairs(at, pairs[i])
                found = np.isfinite(at_end) & np.isfinite(at_start)
                row["n_flight_pairs"] = int(found.sum())
                if found.any():
                    gain = (at_end - at_start)[found]
                    row["high_side_gain_mean"] = float(gain.mean())
                    row["high_side_gain_min"] = float(gain.min())
                    row["tag_index_end"] = float((at_end[found] > 0).mean())
                    row["high_side_end_mean"] = float(at_end[found].mean())
                    row["flight_secs"] = (target - start) / FPS
        rows.append(row)
    return pd.DataFrame(rows)


FLIGHT_FEATURES = (
    "high_side_gain_mean", "high_side_gain_min", "tag_index_end", "high_side_end_mean",
)


# ------------------------------------------------------------------ approach kinematics (F6)

APPROACH_LEAD_FRAMES = 12   # about 0.5 s before the rebound
MIN_APPROACH_SPEED = 2.0    # ft/s; below this a heading is noise, not an approach
COMMITTED_ANGLE_DEG = 60.0


def approach_angles(frames: GameFrames) -> dict[str, np.ndarray]:
    """(N, 10) approach kinematics toward the attacked rim: angle, speed and distance.

    `angle` is the degrees between a player's velocity and the direction from that player
    to the rim: 0 means driving straight at it, 90 means moving across, 180 means running
    away. It is a property of a velocity vector and therefore claims nothing about intent,
    which is the whole reason F6 is built on it. SkillCorner's own position is that tracking
    cannot tell a deliberate crash from a drift; a heading does not have to.

    `angle` is NaN where the player is slower than `MIN_APPROACH_SPEED`, because the
    direction of a near-stationary player is numerically meaningless. The caller reports how
    many rows that removes rather than treating them as zero.
    """
    xy = frames.xy.astype(np.float64)
    v = frames.v.astype(np.float64)
    speed = np.linalg.norm(v, axis=-1)

    to_rim = ATTACKED_HOOP[None, None, :] - xy
    rim_dist = np.linalg.norm(to_rim, axis=-1)
    to_rim_u = np.divide(to_rim, rim_dist[..., None], out=np.zeros_like(to_rim),
                         where=rim_dist[..., None] > 0)
    v_u = np.divide(v, speed[..., None], out=np.zeros_like(v), where=speed[..., None] > 0)
    cos = np.clip((v_u * to_rim_u).sum(axis=-1), -1.0, 1.0)

    angle = np.degrees(np.arccos(cos))
    angle[speed < MIN_APPROACH_SPEED] = np.nan
    return {"angle": angle, "speed": speed, "rim_dist": rim_dist}
