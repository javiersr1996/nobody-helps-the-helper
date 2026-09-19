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
from scbasket.validation import hoop_distance
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


# --------------------------------------------------------------- the shot-scaled zone (P7.2)

#: Share of rebounds the zone is built to hold. Chosen as the coverage of the constant 8 ft
#: band this replaces (0.745 on the calibration games), rounded to 0.75, so the two zones are
#: compared at equal overall coverage and the only thing that can differ is WHERE they hold it.
ZONE_COVERAGE = 0.75

#: r(d) = ZONE_INTERCEPT_FT + ZONE_SLOPE * d, d the shot's distance to the rim, both in feet.
#: FROZEN on the CALIBRATION games on 2026-09-17 and committed before any held-out game was
#: read (D11). Fitted by minimising the pinball loss at ZONE_COVERAGE over a deliberately
#: coarse grid (0.1 ft on the intercept, 0.01 on the slope) across 325 located calibration
#: rebounds; two significant figures is all a sample that size supports.
#: `scripts/rebound_zone.py --fit` re-derives them from the data and prints both.
ZONE_INTERCEPT_FT = 5.40
ZONE_SLOPE = 0.180


def zone_radius(shot_distance) -> np.ndarray:
    """Feet from the rim of the zone a shot taken `shot_distance` feet out earns.

    The constant 8 ft band the earlier work used holds 75% of the calibration rebounds
    overall, but it holds 0.885 of them on shots from inside 8 ft and 0.655 in mid-range: too
    generous on a close miss, too tight on everything else. This line holds the same share
    overall with half that drift across the bands.

    It DESCRIBES where the ball lands given the shot. It says nothing about where a player
    should have been, and nothing about anyone's intention, which is the same footing the
    rest of this layer stands on.
    """
    return ZONE_INTERCEPT_FT + ZONE_SLOPE * np.asarray(shot_distance, dtype=np.float64)


def rebound_zone_table(shots: pd.DataFrame, rebounds: pd.DataFrame) -> pd.DataFrame:
    """One row per rebound: where it landed, and the zone the shot it came from earned.

    Columns: `rebound_id`, `shot_id`, `reb_dist` (feet from the attacked rim to the rebound's
    published location), `shot_dist` (the same for the shot), `zone_ft`, `zone_ratio`
    (`reb_dist` in units of that zone, so 1.0 is exactly on its edge), `in_zone`, `three` and
    `defensive`.

    Both locations come from the event tables, which court.py establishes are already in the
    attacking frame, so neither is re-oriented here. A rebound with no location, or whose shot
    has none, keeps its row with NaN in the measured columns and pd.NA in `in_zone`: on the
    calibration games that is 84 of 409 rebounds, 67 missing their own location and 17 more
    their shot's. The caller reports that count rather than quietly counting them as outside.
    """
    by_id = shots.set_index("id")
    reb_dist = hoop_distance(rebounds["location"])
    shot_dist = hoop_distance(rebounds["shotId"].map(by_id["location"]))
    zone_ft = zone_radius(shot_dist)
    ratio = reb_dist / zone_ft
    return pd.DataFrame({
        "rebound_id": rebounds["id"].to_numpy(),
        "shot_id": rebounds["shotId"].to_numpy(),
        "reb_dist": reb_dist,
        "shot_dist": shot_dist,
        "zone_ft": zone_ft,
        "zone_ratio": ratio,
        "in_zone": pd.Series(ratio <= 1.0, dtype="boolean").mask(np.isnan(ratio)),
        "three": rebounds["shotId"].map(by_id["three"]).astype("boolean").to_numpy(),
        "defensive": rebounds["defensive"].astype("boolean").to_numpy(),
    })


# ------------------------------------------------- the ball's entry angle at the rim (P7.7)

RIM_HEIGHT_FT = 10.0
#: Frames of fall fitted for the angle, about 0.2 s at 25 fps. It is a chord over the last
#: part of the descent rather than a two-frame derivative, which at this frame rate is mostly
#: noise. The ORDERING it produces barely moves with this number (Spearman 0.96 between a
#: 3-frame and an 8-frame window on the 300 calibration rebounds that have one); the median
#: angle does, from 47.3 to 38.7 degrees, so the level is a property of the definition and
#: only the ordering is a property of the ball. Every claim here is built on the ordering.
ENTRY_WINDOW_FRAMES = 5
#: Above this the ball did not fly from the shot to the rebound. 4 s at 25 fps.
MAX_ENTRY_FLIGHT_FRAMES = 100
#: Below this the window cannot hold an apex and a fall.
MIN_ENTRY_FLIGHT_FRAMES = 6
#: The apex has to clear the rim by this much or the ball never came DOWN to rim height.
MIN_APEX_CLEARANCE_FT = 0.5

ENTRY_COLUMNS = ("rebound_id", "shot_id", "entry_angle", "apex_ft", "entry_drop_ft",
                 "entry_run_ft", "cross_dist_ft", "flight_frames", "reason")


def _entry_angle_of(ball: np.ndarray) -> dict:
    """The angle, and the two legs it is built from, for one (K, 3) ball track.

    The angle is measured at the FIRST downward crossing of rim height after the apex, so a
    bounce that sends the ball back up cannot be mistaken for the arrival: measuring the
    departure would predict the landing spot from the ball already travelling there.

    What it does NOT guarantee, measured on 2026-09-19 and stated here because the earlier
    version of this docstring claimed the opposite: the ball may ALREADY be in contact with
    the rim at that crossing. On 15.3% of calibration rows and 12.6% of held-out rows the
    ball centre is within a ball plus a rim radius of the rim axis, or the fitted window
    falls less than half a foot, which is a ball rolling on the ring rather than arriving at
    it. `cross_dist` says how far from the rim the measurement was taken, so a caller can
    exclude those rather than trust the angle blindly; `drop` and `run` are returned for the
    same reason, because the angle's predictive power turned out to live in `run`.
    """
    z = ball[:, 2]
    apex = int(np.argmax(z))
    out = {"angle": np.nan, "apex": float(z[apex]), "drop": np.nan, "run": np.nan,
           "cross_dist": np.nan, "reason": ""}
    if z[apex] < RIM_HEIGHT_FT + MIN_APEX_CLEARANCE_FT:
        return {**out, "reason": "no arc above the rim"}

    below = np.flatnonzero(z[apex:] < RIM_HEIGHT_FT)
    if below.size == 0:
        return {**out, "reason": "never falls back to rim height"}

    crossing = apex + int(below[0])
    out["cross_dist"] = float(np.linalg.norm(ball[crossing, :2] - ATTACKED_HOOP))
    seg = np.arange(max(apex, crossing - ENTRY_WINDOW_FRAMES), crossing + 1)
    if seg.size < 3:
        return {**out, "reason": "fall too short to fit"}

    drop = float(z[seg[0]] - z[seg[-1]])
    if drop <= 0:
        return {**out, "reason": "not falling"}
    run = float(np.linalg.norm(ball[seg[-1], :2] - ball[seg[0], :2]))
    angle = 90.0 if run == 0 else float(np.degrees(np.arctan2(drop, run)))
    return {**out, "angle": angle, "drop": drop, "run": run}


def ball_entry_table(
    frames: GameFrames, shots: pd.DataFrame, rebounds: pd.DataFrame
) -> pd.DataFrame:
    """One row per rebound: how steeply the ball was falling when it reached rim height.

    Columns are `ENTRY_COLUMNS`. `entry_angle` is degrees below horizontal, 0 for a ball
    arriving flat and 90 for one dropping vertically, measured at the first downward crossing
    of rim height. `entry_drop_ft` and `entry_run_ft` are the two legs it is built from and
    `cross_dist_ft` is how far from the rim that crossing happened: all three are published
    because the angle alone hides which of them is doing the work, and on this data it is
    `entry_run_ft`. `reason` says why an angle is NaN and is empty when there is one, so a
    caller counts the losses instead of inferring them.

    The flight is the cached live frames from the shot's `endFrame` to the rebound's `frame`.
    Frames D12 already dropped are simply absent, which is why a flight can be too short.

    Like every other quantity in this module it is a DEFINITION, not a detector: it describes
    a trajectory and asserts nothing about anyone's intention.
    """
    by_id = shots.set_index("id")["endFrame"] if len(shots) else pd.Series(dtype=float)
    row_of = {int(f): i for i, f in enumerate(frames.frame_idx)}
    ball = frames.ball.astype(np.float64)

    rows = []
    for rebound_id, shot_id, frame in zip(
        rebounds["id"], rebounds["shotId"], rebounds["frame"], strict=True
    ):
        row = {"rebound_id": rebound_id, "shot_id": shot_id, "entry_angle": np.nan,
               "apex_ft": np.nan, "entry_drop_ft": np.nan, "entry_run_ft": np.nan,
               "cross_dist_ft": np.nan, "flight_frames": 0, "reason": "no shot or no frame"}
        release = by_id.get(shot_id, np.nan) if pd.notna(shot_id) else np.nan
        if pd.notna(release) and pd.notna(frame):
            lo, hi = int(release), int(frame)
            want = [row_of[f] for f in range(lo, hi + 1) if f in row_of]
            row["flight_frames"] = len(want)
            if hi - lo > MAX_ENTRY_FLIGHT_FRAMES:
                row["reason"] = "flight too long to be one"
            elif len(want) < MIN_ENTRY_FLIGHT_FRAMES:
                row["reason"] = "too few cached frames"
            else:
                got = _entry_angle_of(ball[want])
                row.update(entry_angle=got["angle"], apex_ft=got["apex"],
                           entry_drop_ft=got["drop"], entry_run_ft=got["run"],
                           cross_dist_ft=got["cross_dist"], reason=got["reason"])
        rows.append(row)
    return pd.DataFrame(rows, columns=list(ENTRY_COLUMNS))


# --------------------------------------------------------------- which side it lands on (P7.7)


def side_bias_table(shots: pd.DataFrame, rebounds: pd.DataFrame) -> pd.DataFrame:
    """One row per rebound: the side the shot came from, the side it landed on, and `opposite`.

    Sides are the sign of y in the attacking frame, which court.py establishes the event
    locations are already in. A shot from the middle of the floor has no meaningful side and
    is kept anyway, contributing close to a coin flip: that pulls every share toward 0.5 and
    therefore UNDERSTATES any bias rather than manufacturing one. No minimum |y| is applied,
    because a threshold there is a free parameter and this is a descriptive table.

    `opposite` is pd.NA where either location is missing or either y is exactly zero.
    """
    by_id = shots.set_index("id")
    loc = rebounds["shotId"].map(by_id["location"])
    shot_xy = np.full((len(rebounds), 2), np.nan)
    have = loc.notna().to_numpy()
    if have.any():
        shot_xy[have] = np.array(loc[have].tolist(), dtype=float)
    reb_xy = np.full((len(rebounds), 2), np.nan)
    have_reb = rebounds["location"].notna().to_numpy()
    if have_reb.any():
        reb_xy[have_reb] = np.array(rebounds["location"][have_reb].tolist(), dtype=float)

    shot_y, reb_y = shot_xy[:, 1], reb_xy[:, 1]
    opposite = np.sign(shot_y) != np.sign(reb_y)
    unknown = np.isnan(shot_y) | np.isnan(reb_y) | (shot_y == 0) | (reb_y == 0)
    return pd.DataFrame({
        "rebound_id": rebounds["id"].to_numpy(),
        "shot_id": rebounds["shotId"].to_numpy(),
        "shot_y": shot_y,
        "reb_y": reb_y,
        "shot_dist": hoop_distance(rebounds["shotId"].map(by_id["location"])),
        "three": rebounds["shotId"].map(by_id["three"]).astype("boolean").to_numpy(),
        "opposite": pd.Series(opposite, dtype="boolean").mask(unknown),
    })
