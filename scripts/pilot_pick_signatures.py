"""Feasibility pilot for P3.4: can the control field discriminate pick-and-roll coverage?

Usage: uv run python scripts/pilot_pick_signatures.py [--root DIR] [--cache DIR] [--out DIR]
                                                        [--params FILE] [--shuffles N]

Runs on the five CALIBRATION games only (D11: the held-out games stay shut until P3.4's
thresholds are pre-registered and committed). Nothing here is tuned: the window, the
features, the classifier, the baselines and the permutation statistic are fixed below and
every number is reported as it falls. Writes {out}/pilot_pick_signatures.csv and prints a
verdict against the criterion P3.4 states (accuracy >= majority + 10 points).

What it computes, per pick with a labelled coverage and a complete cached window:

1. Control-field features at the frozen parameters ({out}/control_params.json), sampled at
   5 Hz over [-1 s, +2 s] around picks.frame (16 instants): epc_share; the value-weighted
   share of the paint; the value-weighted share of the threes on the screen side and on the
   weak side (y mirrored per pick so that the screener sits at positive y relative to the
   ball handler at the pick frame, as P3.4 specifies); and P_off at the ball handler, at the
   screener and along the roll lane (the screener-hoop segment). 7 features x 16 instants.
2. Two trivial baselines that carry no control field: the pick's location alone
   (locationType one-hot, distance of the provider's location to the hoop, |y|) and the same
   plus the five raw pairwise distances among the four players involved at every instant.
   F1's lesson: a label derived from geometry is reproduced, not explained, by a model that
   only re-encodes that geometry. The coverage labels are annotated from who guards whom,
   which is exactly what those distances carry.
3. A nearest-centroid classifier (z-scored on the training games, Euclidean) evaluated
   LEAVE-ONE-GAME-OUT, against the majority class of the training games, for bhrDefType and
   then scrDefType. Every fold is printed: a pooled figure hides game-dependent effects, which
   is what cost F1 its conclusion. Balanced accuracy is printed next to it because a nearest
   centroid does not favour the majority class the way accuracy does.
4. A permutation test on the one-vs-rest distance between class centroids, shuffling labels
   WITHIN game, reported pooled and per game.

Classes with fewer than MIN_CLASS_SUPPORT picks over the five games (ice, blitz, none) are
counted in the balance report but not classified: no centroid can be estimated for them from
four training games. The two label sets are coupled by construction (switch, ice and blitz
are the same call on both players); the cross-tabulation shows it.

No unit tests: this is a throw-away pilot that adds nothing to src/scbasket/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scbasket.control import ControlParams, control_at_points, control_field
from scbasket.court import HOOP_X, Grid, make_grid
from scbasket.epc import epc_share
from scbasket.frames import N_SIDE, GameFrames, load_npz
from scbasket.io import Dataset
from scbasket.validation import CALIBRATION_GAMES, hoop_distance, permutation_pvalue
from scbasket.value import ValueSurface, league_zone_values, surface_from_zones

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "opendata-basketball"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"
GRID_FT = 1.0  # D4's default

FPS = 25
WINDOW_OFFSETS = np.arange(-1 * FPS, 2 * FPS + 1, FPS // 5)  # [-1 s, +2 s] at 5 Hz: 16 instants
PICK_INSTANT = int(np.flatnonzero(WINDOW_OFFSETS == 0)[0])  # index of picks.frame in the window
ROLL_LANE_FRACTIONS = (0.1, 0.3, 0.5, 0.7, 0.9)  # sampling of the screener-hoop segment
MIN_CLASS_SUPPORT = 20  # picks over the five games below which a class is not classified
ACCURACY_MARGIN = 0.10  # P3.4: accuracy >= majority + 10 points
P_THRESHOLD = 0.01  # P3.4: p < 0.01 by permutation, one class against the rest
SEED = 0

# The provider's label sets (docs/data_dictionary/picks.md), used for the balance report.
BHR_TYPES = ("none", "ice", "switch", "over", "blitz", "under")
SCR_TYPES = ("none", "ice", "soft", "switch", "blitz", "show")
LOCATION_TYPES = ("middle", "wing", "stepUp")
PLAYER_COLUMNS = ("ballhandlerId", "screenerId", "ballhandlerDefId", "screenerDefId")

FIELD_FEATURES = (
    "epc_share", "paint_share", "three_screen_side", "three_weak_side",
    "p_off_handler", "p_off_screener", "p_off_roll_lane",
)
DISTANCE_FEATURES = ("d_bh_bhdef", "d_scr_scrdef", "d_bh_scr", "d_bh_scrdef", "d_scr_bhdef")
LOCATION_FEATURES = tuple(f"loc_{t}" for t in LOCATION_TYPES) + ("hoop_dist", "abs_y")


# --------------------------------------------------------------------------- windows


def pick_windows(
    frames: GameFrames, picks: pd.DataFrame
) -> tuple[pd.DataFrame, GameFrames, np.ndarray, np.ndarray]:
    """Picks with a complete cached window and all four players resolved at every instant.

    Returns the kept picks, the window rows (n * 16, pick-major, offsets ascending), the
    (n * 16, 4) slots of ball handler and screener (attacker block) and of their defenders
    (defender block), and a (n,) bool of which input picks were kept.
    """
    if np.any(np.diff(frames.frame_idx) < 0):
        raise ValueError("frame_idx is not ascending; pick_windows relies on stream order")
    base = picks["frame"].to_numpy(dtype=np.int64)
    wanted = (base[:, None] + WINDOW_OFFSETS[None, :]).ravel()
    have = frames.frame_idx.astype(np.int64)
    pos = np.minimum(np.searchsorted(have, wanted), len(have) - 1)
    found = (have[pos] == wanted).reshape(len(picks), -1)
    rows = pos.reshape(len(picks), -1)

    ids = picks[list(PLAYER_COLUMNS)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    off, de = frames.off_ids[rows], frames.def_ids[rows]
    hits = [block == ids[:, k, None, None] for k, block in enumerate((off, off, de, de))]
    resolved = np.all([h.any(axis=-1) for h in hits], axis=0)  # (n, 16)
    keep = found.all(axis=1) & resolved.all(axis=1)

    slots = np.stack([h.argmax(axis=-1) for h in hits], axis=-1)[keep].reshape(-1, len(hits))
    window = frames.take(rows[keep].ravel())
    return picks[keep].reset_index(drop=True), window, slots, keep


def screen_side(window: GameFrames, slots: np.ndarray) -> np.ndarray:
    """+1 / -1 per pick: the sign of y of the screener relative to the ball handler at the pick
    frame. Mirroring y by this sign puts the screen side at positive y (P3.4)."""
    n_inst = len(WINDOW_OFFSETS)
    at_pick = np.arange(PICK_INSTANT, len(window), n_inst)
    handler_y = window.xy[at_pick, slots[at_pick, 0], 1]
    screener_y = window.xy[at_pick, slots[at_pick, 1], 1]
    return np.where(screener_y >= handler_y, 1.0, -1.0)


# --------------------------------------------------------------------------- features


def field_features(
    window: GameFrames, slots: np.ndarray, side: np.ndarray, grid: Grid,
    surface: ValueSurface, params: ControlParams,
) -> np.ndarray:
    """(n, 16, 7) control-field features per pick and instant, in FIELD_FEATURES order.

    Zone shares are value-weighted means of P_off over the zone's cells (the epc_share
    formula restricted to the zone), so each lies in [0, 1]. The side split uses the grid's
    y sign against the pick's `side`, which is the mirroring in y without touching the frames.
    """
    n_inst = len(WINDOW_OFFSETS)
    field = control_field(window, grid, params)
    values = np.asarray(surface.values, dtype=np.float64)

    def share(mask: np.ndarray) -> np.ndarray:
        return (field[:, mask] * values[mask]).sum(axis=1) / values[mask].sum()

    paint = np.isin(grid.zone, ("restricted_area", "paint_non_ra"))
    three = np.isin(grid.zone, ("corner_3", "wing_3", "top_3"))
    positive_y = grid.centers[:, 1] > 0
    three_pos, three_neg = share(three & positive_y), share(three & ~positive_y)
    row_side = np.repeat(side, n_inst)
    three_screen = np.where(row_side > 0, three_pos, three_neg)
    three_weak = np.where(row_side > 0, three_neg, three_pos)

    rows = np.arange(len(window))
    handler_xy = window.xy[rows, slots[:, 0]].astype(np.float64)
    screener_xy = window.xy[rows, slots[:, 1]].astype(np.float64)
    hoop = np.array([HOOP_X, 0.0])
    lane = np.mean(
        [control_at_points(window, screener_xy + f * (hoop - screener_xy), params)
         for f in ROLL_LANE_FRACTIONS],
        axis=0,
    )
    feats = np.column_stack([
        epc_share(field, surface), share(paint), three_screen, three_weak,
        control_at_points(window, handler_xy, params),
        control_at_points(window, screener_xy, params),
        lane,
    ])
    return feats.reshape(-1, n_inst, len(FIELD_FEATURES))


def distance_features(window: GameFrames, slots: np.ndarray) -> np.ndarray:
    """(n, 16, 5) raw pairwise distances among the four players, in DISTANCE_FEATURES order."""
    rows = np.arange(len(window))
    xy = window.xy.astype(np.float64)
    bh, scr = xy[rows, slots[:, 0]], xy[rows, slots[:, 1]]
    bhdef, scrdef = xy[rows, N_SIDE + slots[:, 2]], xy[rows, N_SIDE + slots[:, 3]]
    pairs = ((bh, bhdef), (scr, scrdef), (bh, scr), (bh, scrdef), (scr, bhdef))
    dist = np.column_stack([np.linalg.norm(a - b, axis=1) for a, b in pairs])
    return dist.reshape(-1, len(WINDOW_OFFSETS), len(DISTANCE_FEATURES))


def location_features(picks: pd.DataFrame) -> np.ndarray:
    """(n, 5) location of the pick from the event table alone, in LOCATION_FEATURES order."""
    one_hot = np.column_stack(
        [(picks["locationType"] == t).to_numpy(float) for t in LOCATION_TYPES]
    )
    location = np.array(picks["location"].tolist(), dtype=float)
    return np.column_stack([one_hot, hoop_distance(picks["location"]), np.abs(location[:, 1])])


def flatten(per_instant: np.ndarray, names: tuple[str, ...]) -> tuple[np.ndarray, list[str]]:
    """(n, 16, k) -> (n, 16 * k) with one column name per feature and instant."""
    n = per_instant.shape[0]
    columns = [f"{name}@{off / FPS:+.1f}s" for off in WINDOW_OFFSETS for name in names]
    return per_instant.reshape(n, -1), columns


# --------------------------------------------------------------------------- classifier


def _zscore(x: np.ndarray, train: np.ndarray) -> np.ndarray:
    mu, sd = x[train].mean(axis=0), x[train].std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (x - mu) / sd


def nearest_centroid_logo(
    x: np.ndarray, y: np.ndarray, game: np.ndarray, classes: tuple[str, ...]
) -> pd.DataFrame:
    """Leave-one-game-out nearest centroid: one row per held-out game.

    Features are z-scored with the training games' mean and standard deviation; a class
    absent from the training games gets no centroid (infinite distance). `majority` is the
    accuracy of always predicting the training games' most frequent class on the held-out
    game; `own_majority` is the held-out game's own top class share, the oracle version.
    """
    out = []
    for held in np.unique(game):
        train, test = game != held, game == held
        z = _zscore(x, train)
        centroids = np.full((len(classes), x.shape[1]), np.inf)
        counts = np.array([(y[train] == c).sum() for c in classes])
        for k, c in enumerate(classes):
            if counts[k]:
                centroids[k] = z[train & (y == c)].mean(axis=0)
        dist = ((z[test][:, None, :] - centroids[None]) ** 2).sum(axis=-1)
        pred = np.array(classes)[dist.argmin(axis=1)]
        truth = y[test]
        recalls = [(pred[truth == c] == c).mean() for c in classes if (truth == c).any()]
        majority_class = classes[int(counts.argmax())]
        own = max((truth == c).mean() for c in classes)
        out.append({
            "game": int(held), "n": int(test.sum()), "accuracy": float((pred == truth).mean()),
            "balanced_accuracy": float(np.mean(recalls)),
            "majority": float((truth == majority_class).mean()),
            "majority_class": majority_class, "own_majority": float(own),
        })
    return pd.DataFrame(out)


def eta_squared(x: np.ndarray, y: np.ndarray, classes: tuple[str, ...]) -> np.ndarray:
    """Between-class share of each column's variance (one-way eta squared): 0 means the class
    does not move the feature at all, 1 means it explains it entirely."""
    grand = x.mean(axis=0)
    between = sum((y == c).sum() * (x[y == c].mean(axis=0) - grand) ** 2 for c in classes)
    total = ((x - grand) ** 2).sum(axis=0)
    return np.where(total > 0, between / np.where(total > 0, total, 1.0), 0.0)


def centroid_gap(z: np.ndarray, mask: np.ndarray) -> float:
    """Euclidean distance between the centroid of the masked rows and of the rest."""
    if not mask.any() or mask.all():
        return float("nan")
    return float(np.linalg.norm(z[mask].mean(axis=0) - z[~mask].mean(axis=0)))


def permutation_gap(
    z: np.ndarray, mask: np.ndarray, game: np.ndarray, shuffles: int, rng: np.random.Generator
) -> tuple[float, float]:
    """Observed one-vs-rest centroid gap and its permutation p-value, shuffling within game."""
    observed = centroid_gap(z, mask)
    groups = [np.flatnonzero(game == g) for g in np.unique(game)]
    null = np.empty(shuffles)
    for i in range(shuffles):
        perm = mask.copy()
        for idx in groups:
            perm[idx] = mask[idx][rng.permutation(len(idx))]
        null[i] = centroid_gap(z, perm)
    return observed, permutation_pvalue(observed, null)


# --------------------------------------------------------------------------- report


def balance(picks: pd.DataFrame, column: str, types: tuple[str, ...]) -> pd.Series:
    counts = picks[column].value_counts()
    extra = sorted(set(counts.index) - set(types))
    return counts.reindex(list(types) + extra, fill_value=0)


def fmt(x: float) -> str:
    return f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DATA, help="opendata-basketball clone")
    parser.add_argument("--cache", type=Path, default=INTERIM, help="D12 frame cache directory")
    parser.add_argument("--out", type=Path, default=REPORTS, help="reports directory")
    parser.add_argument("--params", type=Path, default=None,
                        help="frozen parameters (default: {out}/control_params.json)")
    parser.add_argument("--shuffles", type=int, default=2000, help="permutation draws")
    args = parser.parse_args(argv)
    params_path = args.params or args.out / "control_params.json"
    frozen = json.loads(params_path.read_text(encoding="utf-8"))
    params = ControlParams(**frozen["params"])
    print(f"calibration games only (D11): {list(CALIBRATION_GAMES)}; frozen parameters "
          f"{frozen['params']} from {params_path.name}; window "
          f"[{WINDOW_OFFSETS[0] / FPS:+.0f} s, {WINDOW_OFFSETS[-1] / FPS:+.0f} s] at 5 Hz, "
          f"{len(WINDOW_OFFSETS)} instants")

    dataset = Dataset(args.root)
    grid = make_grid(GRID_FT)
    surface = surface_from_zones(grid, league_zone_values(dataset.aggregates("shots")))

    # ---- 1. picks, windows, features
    t0 = time.perf_counter()
    kept, fields, dists = [], [], []
    n_events = n_cached = n_no_location = 0
    for game_id in CALIBRATION_GAMES:
        picks = dataset.events(game_id)["picks"]
        frames = load_npz(args.cache / f"{game_id}_frames.npz")
        n_events += len(picks)
        n_cached += int(np.isin(picks["frame"].to_numpy(), frames.frame_idx).sum())
        has_location = picks["location"].notna() & picks["locationType"].notna()
        n_no_location += int((~has_location).sum())
        picks, window, slots, _ = pick_windows(frames, picks[has_location].reset_index(drop=True))
        side = screen_side(window, slots)
        fields.append(field_features(window, slots, side, grid, surface, params))
        dists.append(distance_features(window, slots))
        kept.append(picks.assign(game_id=game_id, side=side))
    picks = pd.concat(kept, ignore_index=True)
    field_x, field_names = flatten(np.concatenate(fields), FIELD_FEATURES)
    dist_x, dist_names = flatten(np.concatenate(dists), DISTANCE_FEATURES)
    loc_x = location_features(picks)
    game = picks["game_id"].to_numpy()
    print(f"\npicks: {n_events} events, {n_cached} with picks.frame in the D12 cache, "
          f"{n_no_location} without a location, {len(picks)} with the full window cached and "
          f"the four players resolved at every instant (features in "
          f"{time.perf_counter() - t0:.1f} s). P3.4 asks for >= 1,000 over 10 games.")
    print(f"per game: {picks.groupby('game_id').size().to_dict()}")
    print(f"screen side at the pick frame: {int((picks['side'] > 0).sum())} left (+y), "
          f"{int((picks['side'] < 0).sum())} right (-y), mirrored so the screen side is +y")

    print("\nclass balance on the usable picks (provider's label sets, in dictionary order):")
    for column, types in (("bhrDefType", BHR_TYPES), ("scrDefType", SCR_TYPES)):
        counts = balance(picks, column, types)
        shares = " ".join(f"{t} {n} ({n / len(picks):.1%})" for t, n in counts.items())
        print(f"  {column}: {shares}")
    print("  cross-tabulation (the two label sets are coupled: switch, ice and blitz are the "
          "same call on both players):")
    cross = pd.crosstab(picks["bhrDefType"], picks["scrDefType"])
    print("    " + cross.to_string().replace("\n", "\n    "))

    feature_sets = {
        "location": (loc_x, list(LOCATION_FEATURES)),
        "location+distances": (
            np.column_stack([loc_x, dist_x]), list(LOCATION_FEATURES) + dist_names
        ),
        "field": (field_x, field_names),
        "field+location+distances": (
            np.column_stack([field_x, loc_x, dist_x]),
            field_names + list(LOCATION_FEATURES) + dist_names,
        ),
    }
    records = []

    # ---- 2. leave-one-game-out nearest centroid, bhrDefType first
    verdicts = {}
    for column in ("bhrDefType", "scrDefType"):
        y_all = picks[column].to_numpy(dtype=str)
        support = picks[column].value_counts()
        classes = tuple(c for c in support.index if support[c] >= MIN_CLASS_SUPPORT)
        use = np.isin(y_all, classes)
        y, g = y_all[use], game[use]
        dropped = sorted(str(c) for c in set(y_all) - set(classes))
        print(f"\n== {column}: nearest centroid, leave-one-game-out, classes {list(classes)} "
              f"(n = {int(use.sum())}; {dropped} below {MIN_CLASS_SUPPORT} picks, not classified)")
        folds = {}
        for name, (x, _) in feature_sets.items():
            folds[name] = nearest_centroid_logo(x[use], y, g, classes)
        base = folds["field"]
        header = "  " + f"{'feature set':<26}" + "".join(f"{int(gm):>9}" for gm in base["game"])
        print(header + f"{'mean':>9}{'bal.acc':>9}")
        majority = "".join(f"{v:>9.3f}" for v in base["majority"])
        print("  " + f"{'majority (train class)':<26}" + majority
              + f"{base['majority'].mean():>9.3f}{'':>9}  "
              + f"[{', '.join(base['majority_class'])}]")
        own = "".join(f"{v:>9.3f}" for v in base["own_majority"])
        print("  " + f"{'own majority (oracle)':<26}" + own
              + f"{base['own_majority'].mean():>9.3f}")
        for name, table in folds.items():
            beats = int((table["accuracy"] > table["majority"]).sum())
            print("  " + f"{name:<26}" + "".join(f"{v:>9.3f}" for v in table["accuracy"])
                  + f"{table['accuracy'].mean():>9.3f}{table['balanced_accuracy'].mean():>9.3f}  "
                  f"above majority in {beats} of {len(table)} folds")
            for row in table.itertuples():
                for metric in ("accuracy", "balanced_accuracy", "majority", "own_majority"):
                    records.append({
                        "label": column, "feature_set": name, "game": row.game, "class": "",
                        "metric": metric, "feature": "", "instant_s": np.nan,
                        "value": getattr(row, metric), "p_value": np.nan, "n": row.n,
                    })
        mean_acc = base["accuracy"].mean()
        mean_maj = base["majority"].mean()
        verdicts[column] = {
            "accuracy": mean_acc, "majority": mean_maj, "own_majority": base["own_majority"].mean(),
            "baseline": folds["location+distances"]["accuracy"].mean(),
            "combined": folds["field+location+distances"]["accuracy"].mean(),
            "criterion": mean_acc >= mean_maj + ACCURACY_MARGIN,
            "beats_majority_folds": int((base["accuracy"] > base["majority"]).sum()),
            "field_vs_baseline_folds": int(
                (base["accuracy"] > folds["location+distances"]["accuracy"]).sum()
            ),
            "combined_vs_baseline_folds": int(
                (folds["field+location+distances"]["accuracy"]
                 > folds["location+distances"]["accuracy"]).sum()
            ),
        }

        # ---- 3. permutation of the one-vs-rest centroid gap, within-game shuffles
        rng = np.random.default_rng(SEED)
        print(f"  one-vs-rest centroid gap (z-scored features), permutation p with "
              f"{args.shuffles} within-game shuffles: pooled, then per game")
        print("  " + f"{'feature set':<26}{'class':<8}{'gap':>7}{'p':>8}"
              + "".join(f"{int(gm):>9}" for gm in np.unique(g)))
        significant = {}
        for name in ("field", "location+distances"):
            x = feature_sets[name][0][use]
            z = _zscore(x, np.ones(len(x), bool))
            for c in classes:
                mask = y == c
                gap, p = permutation_gap(z, mask, g, args.shuffles, rng)
                per_game = []
                for held in np.unique(g):
                    sel = g == held
                    gap_g, p_g = permutation_gap(z[sel], mask[sel], g[sel], args.shuffles, rng)
                    per_game.append((held, gap_g, p_g))
                    records.append({
                        "label": column, "feature_set": name, "game": int(held), "class": c,
                        "metric": "centroid_gap", "feature": "", "instant_s": np.nan,
                        "value": gap_g, "p_value": p_g, "n": int(sel.sum()),
                    })
                records.append({
                    "label": column, "feature_set": name, "game": 0, "class": c,
                    "metric": "centroid_gap", "feature": "", "instant_s": np.nan,
                    "value": gap, "p_value": p, "n": len(y),
                })
                significant.setdefault(name, 0)
                significant[name] += int(p < P_THRESHOLD)
                cells = "".join(f"{p_g:>9.3f}" for _, _, p_g in per_game)
                print("  " + f"{name:<26}{c:<8}{gap:>7.3f}{p:>8.4f}" + cells)
        verdicts[column]["significant"] = significant

        # ---- 4. effect sizes: how much of each feature's variance the class explains, at the
        # instant where it explains most (lesson from F1: check a quantity can actually vary)
        print("  eta^2 per feature, max over the 16 instants: pooled, then per game "
              "(field features, then the raw distances of the baseline)")
        games = "".join(f"{int(gm):>9}" for gm in np.unique(g))
        print("  " + f"{'feature':<20}{'pooled':>8}" + games)
        for per_instant, names in ((np.concatenate(fields)[use], FIELD_FEATURES),
                                   (np.concatenate(dists)[use], DISTANCE_FEATURES)):
            flat = per_instant.reshape(len(per_instant), -1)
            pooled = eta_squared(flat, y, classes).reshape(len(WINDOW_OFFSETS), -1).max(axis=0)
            per_game = {}
            for held in np.unique(g):
                sel = g == held
                per_game[held] = eta_squared(flat[sel], y[sel], classes).reshape(
                    len(WINDOW_OFFSETS), -1
                ).max(axis=0)
            for j, name in enumerate(names):
                print("  " + f"{name:<20}{pooled[j]:>8.3f}"
                      + "".join(f"{per_game[held][j]:>9.3f}" for held in np.unique(g)))
                for held, values in [(0, pooled), *per_game.items()]:
                    records.append({
                        "label": column, "feature_set": "field" if names is FIELD_FEATURES
                        else "location+distances", "game": int(held), "class": "",
                        "metric": "eta2_max", "feature": name, "instant_s": np.nan,
                        "value": float(values[j]), "p_value": np.nan,
                        "n": int((g == held).sum()) if held else len(y),
                    })

        # ---- 5. signature preview: class means of the field features per instant
        fields_use = np.concatenate(fields)[use]
        for c in classes:
            for j, name in enumerate(FIELD_FEATURES):
                for i, off in enumerate(WINDOW_OFFSETS):
                    records.append({
                        "label": column, "feature_set": "field", "game": 0, "class": c,
                        "metric": "class_mean", "feature": name, "instant_s": off / FPS,
                        "value": float(fields_use[y == c, i, j].mean()), "p_value": np.nan,
                        "n": int((y == c).sum()),
                    })
        show = ("p_off_handler", "p_off_screener", "p_off_roll_lane", "epc_share")
        print(f"  class means at the pick frame and at +2 s ({', '.join(show)}):")
        for c in classes:
            cells = []
            for name in show:
                j = FIELD_FEATURES.index(name)
                at0 = fields_use[y == c, PICK_INSTANT, j].mean()
                at2 = fields_use[y == c, -1, j].mean()
                cells.append(f"{at0:.3f}->{at2:.3f}")
            print(f"    {c:<8}" + "".join(f"{cell:>16}" for cell in cells))

    out_path = args.out / "pilot_pick_signatures.csv"
    pd.DataFrame.from_records(records).to_csv(out_path, index=False)
    print(f"\nwrote {len(records)} rows to {out_path}")

    # ---- verdict
    print("\nverdict against P3.4's criterion (accuracy >= majority + 10 points, mean of the "
          "leave-one-game-out folds; nothing adjusted):")
    for column, v in verdicts.items():
        print(f"  {column}: field {v['accuracy']:.3f} vs training majority {v['majority']:.3f} "
              f"(needs {v['majority'] + ACCURACY_MARGIN:.3f}) -> "
              f"{'PASS' if v['criterion'] else 'FAIL'}; above that majority in "
              f"{v['beats_majority_folds']} of {len(CALIBRATION_GAMES)} folds; the held-out "
              f"game's own majority (oracle) is {v['own_majority']:.3f}")
        print(f"    geometry check: location+distances {v['baseline']:.3f}; the field beats it "
              f"in {v['field_vs_baseline_folds']} folds; field added to it gives "
              f"{v['combined']:.3f}, better in {v['combined_vs_baseline_folds']} folds; classes "
              f"with pooled p < {P_THRESHOLD} one-vs-rest: field {v['significant']['field']}, "
              f"baseline {v['significant']['location+distances']} (per-game p above)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
