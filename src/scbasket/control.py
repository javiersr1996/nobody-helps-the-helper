"""Space control field: Fernández & Bornn (2018) adapted to the half court.

Each player exerts a bivariate Gaussian influence (D1) centred on their position
projected along their velocity (D3), elongated in the direction of travel and
scaled by a radius that grows with the distance to the ball (D2). Offensive
control of a location is the logistic function of the influence surplus of the
offense over the defense. Everything is vectorised in batches of frames over
``(B, 10, G)`` arrays, and the Gaussian is written as an explicit 2x2 quadratic
form: no ``np.linalg``, no scipy.

Influence of player i at location p (feet and seconds throughout):

    d_i          = |xy_i - ball|                                   distance to the ball
    r_i          = r_near + (r_far - r_near) min(d_i / d_far, 1)   influence radius (D2)
    h            = clip(shot_clock, 0, t_h)                        effective horizon (D3)
    mu_i         = xy_i + v_i h                                    projected centre
    e_i          = min(|v_i| / v_max, 1)^2 * h / t_h               elongation, 0 when h = 0
    sigma_along  = r_i (1 + e_i) / 2,   sigma_perp = r_i (1 - e_i) / 2
    I_i(p)       = exp(-q / 2),   q = (p - mu_i)^T Sigma_i^-1 (p - mu_i)

with Sigma_i = R S S R^T, R the rotation onto the unit velocity u_i and S =
diag(sigma_along, sigma_perp). R is orthogonal, so Sigma^-1 = R S^-2 R^T
in closed form, and q expands to a dx^2 + 2 b dx dy + c dy^2 with

    k = 1 / sigma_along^2 - 1 / sigma_perp^2
    a = 1 / sigma_perp^2 + k u_x^2,   b = k u_x u_y,   c = 1 / sigma_perp^2 + k u_y^2.

Control: P_off(p) = sigmoid(slope * (sum_{i in off} I_i(p) - sum_{i in def} I_i(p))).

What is kept from Fernández & Bornn: the Gaussian, its rotation and elongation
by speed (at the reference speed the ellipse collapses onto the direction of
travel), the radius as a function of the distance to the ball, the logistic
combination. ``r`` follows their convention: at rest the standard deviation is
r / 2 on both axes, so the influence has fallen to exp(-2) at distance r.

What is adapted, beyond the units (D2, feet) and the initial values (calibrated
in P1.4, never by eye):

- The elongation is gated by the same horizon as the projection (the ``h / t_h``
  factor). D3 asks that the control be purely positional when the clock has
  expired, and F&B's elongation would still depend on the velocity there. The
  gate is 1 whenever the clock exceeds t_h (nearly every frame at t_h = 0.3 s),
  fades linearly under it, and makes t_h = 0 a clean ablation of the velocity:
  with that setting the model ignores v altogether.
- The influence is normalised to 1 at its centre mu_i (F&B normalise at the
  player's current position), so I_i lies in (0, 1] and the score in [-5, 5].
- sigma_perp is floored at SIGMA_FLOOR_FT so the coefficients stay finite at
  |v| >= v_max, where F&B's ellipse is degenerate. In the 10 cached games 149 of
  5.37 million positions reach 25 ft/s; the floor is a numerical guard, not a
  parameter.

Extrapolated positions (``detected == False``) enter as they are: they are the
provider's best estimate, and their error is propagated by the Monte Carlo of
P1.2 (``control_with_uncertainty``, ``control_at_points_with_uncertainty``), not
by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from scbasket.court import Grid
from scbasket.frames import N_SIDE, GameFrames
from scbasket.quality import sigma_from_pred_error

SIGMA_FLOOR_FT = 1e-3  # floor on the across-track standard deviation (see the module docstring)
REMOVED_XY_FT = 1e6  # where remove_players parks a player: its influence underflows to exactly 0


@dataclass(frozen=True)
class ControlParams:
    """Parameters of the control model: initial values from D2 and D3, calibrated in P1.4.

    r_near / r_far: influence radius (ft) next to the ball and at d_far ft or
    more from it, linear in between; at rest the Gaussian has standard
    deviation r / 2. v_max: speed (ft/s) at which the elongation is complete.
    t_h: projection horizon (s), clipped by the shot clock. slope: gain of the
    logistic function.
    """

    r_near: float = 4.0
    r_far: float = 10.0
    d_far: float = 30.0
    v_max: float = 25.0
    t_h: float = 0.3
    slope: float = 1.0

    def __post_init__(self) -> None:
        if min(self.r_near, self.r_far, self.d_far, self.v_max) <= 0 or self.t_h < 0:
            raise ValueError("r_near, r_far, d_far and v_max must be positive and t_h >= 0")


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Logistic function through tanh: never overflows, and sigmoid(-x) + sigmoid(x) == 1."""
    return 0.5 * (1.0 + np.tanh(0.5 * x))


def _ellipses(
    xy: np.ndarray, v: np.ndarray, ball: np.ndarray, shot_clock: np.ndarray, params: ControlParams
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per-player Gaussian: centre (B, 10, 2) and quadratic-form coefficients a, b, c (B, 10, 1)."""
    xy = np.asarray(xy, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    to_ball = xy - np.asarray(ball, dtype=np.float64)[:, None, :2]
    d_ball = np.sqrt(to_ball[..., 0] ** 2 + to_ball[..., 1] ** 2)  # (B, 10)
    radius = params.r_near + (params.r_far - params.r_near) * np.minimum(d_ball / params.d_far, 1.0)

    horizon = np.clip(np.asarray(shot_clock, dtype=np.float64), 0.0, params.t_h)[:, None]  # (B, 1)
    mu = xy + v * horizon[..., None]
    speed = np.sqrt(v[..., 0] ** 2 + v[..., 1] ** 2)
    gate = horizon / params.t_h if params.t_h > 0 else np.zeros_like(horizon)
    elong = (np.minimum(speed, params.v_max) / params.v_max) ** 2 * gate
    sigma_along = radius * (1.0 + elong) / 2.0
    sigma_perp = np.maximum(radius * (1.0 - elong) / 2.0, SIGMA_FLOOR_FT)

    # Unit direction of travel; (1, 0) at rest, where the ellipse is a circle anyway.
    moving = speed > 0
    safe = np.where(moving, speed, 1.0)
    ux = np.where(moving, v[..., 0] / safe, 1.0)
    uy = np.where(moving, v[..., 1] / safe, 0.0)
    inv_perp = 1.0 / sigma_perp**2
    k = 1.0 / sigma_along**2 - inv_perp  # exactly 0 when the ellipse is a circle
    a = inv_perp + k * ux * ux
    b = k * ux * uy
    c = inv_perp + k * uy * uy
    return mu, a[..., None], b[..., None], c[..., None]


def influence(
    xy: np.ndarray,
    v: np.ndarray,
    ball: np.ndarray,
    shot_clock: np.ndarray,
    points: np.ndarray,
    params: ControlParams,
) -> np.ndarray:
    """Influence of every player at every point, (B, 10, G) in (0, 1]; see the module docstring.

    xy and v are (B, 10, 2), ball (B, 2) or (B, 3) (z ignored), shot_clock (B,).
    points is (G, 2) for locations shared by all frames (a grid) or (B, G, 2) for
    per-frame locations. Computed in float64 whatever the input dtype.
    """
    mu, a, b, c = _ellipses(xy, v, ball, shot_clock, params)
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim == 2:
        pts = pts[None]
    dx = pts[:, None, :, 0] - mu[:, :, 0, None]  # (B, 10, G)
    dy = pts[:, None, :, 1] - mu[:, :, 1, None]
    q = a * dx * dx + 2.0 * b * dx * dy + c * dy * dy
    return np.exp(-0.5 * q)


def _score(
    xy: np.ndarray,
    v: np.ndarray,
    ball: np.ndarray,
    shot_clock: np.ndarray,
    points: np.ndarray,
    params: ControlParams,
) -> np.ndarray:
    """Influence surplus of the offense over the defense, (B, G)."""
    infl = influence(xy, v, ball, shot_clock, points, params)
    return infl[:, :N_SIDE].sum(axis=1) - infl[:, N_SIDE:].sum(axis=1)


def control_field(
    frames: GameFrames, grid: Grid, params: ControlParams, batch: int = 64
) -> np.ndarray:
    """P_off at every grid cell for every frame: (N, G) float64 in [0, 1].

    Frames are processed ``batch`` at a time; the (batch, 10, G) temporaries are
    11.5 MB each at the defaults on a 1 ft grid. The result does not depend on
    ``batch``: every element goes through the same operations in the same order.
    """
    if batch < 1:
        raise ValueError("batch must be >= 1")
    n = len(frames)
    out = np.empty((n, len(grid.centers)), dtype=np.float64)
    for lo in range(0, n, batch):
        rows = slice(lo, lo + batch)
        score = _score(
            frames.xy[rows], frames.v[rows], frames.ball[rows], frames.shot_clock[rows],
            grid.centers, params,
        )
        out[rows] = _sigmoid(params.slope * score)
    return out


def _perturb(frames: GameFrames, rng: np.random.Generator) -> GameFrames:
    """One Monte Carlo draw (D8): a copy of frames with every position displaced by an
    isotropic Gaussian of its own sigma_from_pred_error(frames.pred_error) -- an
    extrapolated position (larger predError) is perturbed more than a detected one.
    Shared by control_with_uncertainty and control_at_points_with_uncertainty; ball,
    velocity, shot_clock and every id are left untouched, exactly like remove_players.
    """
    sigma = sigma_from_pred_error(frames.pred_error).astype(np.float64)  # (N, 10)
    noise = rng.normal(size=(*sigma.shape, 2)) * sigma[..., None]
    xy = (frames.xy.astype(np.float64) + noise).astype(np.float32)
    return replace(frames, xy=xy)


def control_with_uncertainty(
    frames: GameFrames,
    grid: Grid,
    params: ControlParams,
    samples: int = 20,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Mean and standard deviation of control_field over D8's Monte Carlo position error.

    Draws ``samples`` independent perturbations of ``frames`` (see _perturb), evaluates
    control_field on each, and returns (mean, std) over the draws: two (N, G) float64
    arrays, same shape as control_field's output. With predError == 0 everywhere the
    perturbation is exactly zero on every draw, so std is exactly 0 and mean equals
    control_field(frames, grid, params) bit for bit.

    Budget (D8): affordable only on a small number of frames (release, picks) -- this
    costs ``samples`` times control_field's own cost, never the full ~537k D12-filtered
    cache. Callers select event frames first (e.g. scbasket.frames.at_frames) and pass
    only those in.

    Reproducibility: pass an explicit ``rng`` (a numpy.random.Generator); the same seed
    gives the same (mean, std). Without one, a fresh, unseeded generator is used. Global
    numpy random state is never touched.

    The returned std is not uniform over the field: it is largest exactly at cells near a
    sign change of the offense-defense influence surplus, where the sigmoid is steepest --
    the same cells contestLevel calls close. A small position perturbation flips such a
    cell between offense and defense; a cell deep in someone's territory barely moves. This
    is not model noise to average away: it is P1.2's finding, and the same reason
    ``epc_share``/``p_off_shooter`` around a shot's release carry the widest error bars
    exactly where the shot itself is most contested (see scripts/shot_contest_uncertainty.py).
    """
    if samples < 1:
        raise ValueError("samples must be >= 1")
    rng = np.random.default_rng() if rng is None else rng
    fields = np.empty((samples, len(frames), len(grid.centers)), dtype=np.float64)
    for s in range(samples):
        fields[s] = control_field(_perturb(frames, rng), grid, params)
    return fields.mean(axis=0), fields.std(axis=0)


def control_at_points(frames: GameFrames, points: np.ndarray, params: ControlParams) -> np.ndarray:
    """P_off at one location per frame (points is (N, 2), e.g. the shooter at release): (N,).

    Same arithmetic as control_field, so at a cell centre both agree.
    """
    pts = np.asarray(points, dtype=np.float64).reshape(len(frames), 1, 2)
    score = _score(frames.xy, frames.v, frames.ball, frames.shot_clock, pts, params)
    return _sigmoid(params.slope * score[:, 0])


def control_at_points_with_uncertainty(
    frames: GameFrames,
    points: np.ndarray,
    params: ControlParams,
    samples: int = 20,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Mean and standard deviation of control_at_points over D8's Monte Carlo position error.

    The point analogue of control_with_uncertainty, for callers that need a scalar per
    frame rather than a field -- validation.release_features's p_off_std and
    scripts/shot_contest_uncertainty.py's p_off_mean/p_off_std both evaluate P_off at a
    single tracked location (the shooter) per frame, so a (samples, N, G) field would
    compute and discard G - 1 values it never uses. Same perturbation (_perturb), same
    reproducibility guarantees, as control_with_uncertainty.
    """
    if samples < 1:
        raise ValueError("samples must be >= 1")
    rng = np.random.default_rng() if rng is None else rng
    values = np.empty((samples, len(frames)), dtype=np.float64)
    for s in range(samples):
        values[s] = control_at_points(_perturb(frames, rng), points, params)
    return values.mean(axis=0), values.std(axis=0)


def voronoi_field(frames: GameFrames, grid: Grid, batch: int = 64) -> np.ndarray:
    """Nearest-player baseline (D1): (N, G) with 1 where the closest player to the cell is an
    attacker, 0 where it is a defender, 0.5 on an exact tie. Positions only, no velocity."""
    if batch < 1:
        raise ValueError("batch must be >= 1")
    centers = np.asarray(grid.centers, dtype=np.float64)
    n = len(frames)
    out = np.empty((n, len(centers)), dtype=np.float64)
    for lo in range(0, n, batch):
        rows = slice(lo, lo + batch)
        xy = frames.xy[rows].astype(np.float64)
        dx = centers[None, None, :, 0] - xy[:, :, 0, None]  # (B, 10, G)
        dy = centers[None, None, :, 1] - xy[:, :, 1, None]
        d2 = dx * dx + dy * dy
        d_off = d2[:, :N_SIDE].min(axis=1)
        d_def = d2[:, N_SIDE:].min(axis=1)
        out[rows] = np.where(d_off < d_def, 1.0, np.where(d_off > d_def, 0.0, 0.5))
    return out


def remove_players(frames: GameFrames, mask: np.ndarray) -> GameFrames:
    """A copy of frames in which the players flagged in ``mask`` (N, 10) exert no influence.

    The counterfactual frames of D7 ("the same frame without player j"). Rather
    than dropping rows, which would break the fixed 5 + 5 slot layout every
    consumer relies on, a removed player is parked at REMOVED_XY_FT (a million
    feet off court) with zero velocity. There its Gaussian underflows to exactly
    0.0 at every point of the court for any radius under about 1e4 ft, so the
    influence sum of its team loses a non-negative term and nothing else moves:
    the radius of the remaining players depends on the ball, not on teammates.
    The counterfactual is therefore monotone cell by cell, P_off can only rise
    when a defender is removed and only fall when an attacker is, which is what
    ``denied_k >= 0`` in P2.2 rests on. Voronoi and nearest-defender lookups see
    the same thing: a parked player is never the closest to anything on the court.

    ids, ball, ball_holder, matchup, detected and pred_error are left untouched:
    the counterfactual removes the player's body, not the ball they may hold
    (D7 never removes the ball handler), and the remaining radii keep depending
    on where the ball actually is.
    """
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != frames.xy.shape[:2]:
        raise ValueError(f"mask must have shape {frames.xy.shape[:2]}, got {mask.shape}")
    xy = frames.xy.copy()
    v = frames.v.copy()
    xy[mask] = REMOVED_XY_FT
    v[mask] = 0.0
    return replace(frames, xy=xy, v=v)
