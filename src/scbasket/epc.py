"""Expected points controlled (EPC): the value-weighted headline metric of the model (D6).

``epc_share(p_off, surface)`` is the whole-frame share of the court's shot value that sits
under offensive control: ``sum_c P_off(c) V(c) / sum_c V(c)``, in [0, 1]. This is formally
task P2.1's module, but P1.3's ``release_features`` (validation.py) needs the share for its
``epc_share`` column, and duplicating the one-line formula inline there would risk diverging
from the eventual P2.1 implementation. So the module exists now, with only this one function.

``epc_by_zone`` (the per-zone decomposition), ``player_contributions`` and ``chance_series``
are P2.1/P2.2/P3.1 work and get added here later; nothing in this module anticipates them.
"""

from __future__ import annotations

import numpy as np

from scbasket.value import ValueSurface


def epc_share(p_off: np.ndarray, surface: ValueSurface) -> np.ndarray:
    """Share of the court's value under offensive control: sum_c P_off(c) V(c) / sum_c V(c).

    p_off is (N, G): one P_off value per grid cell per frame, over the same grid
    ``surface`` was built on (e.g. ``scbasket.control.control_field``'s output). Cells
    with zero value (backcourt, far, other -- see value.py's _ZERO_VALUE_ZONES) always
    contribute 0 to both the numerator and the denominator, so however much of the field
    is controlled there, it cannot move the share.

    Raises ValueError if p_off's cell count does not match surface.values. Returns (N,)
    of NaN if the surface carries no value at all (sum_c V(c) == 0), rather than dividing
    by zero.
    """
    values = np.asarray(surface.values, dtype=np.float64)
    p_off = np.asarray(p_off, dtype=np.float64)
    if p_off.ndim != 2 or p_off.shape[1] != values.shape[0]:
        raise ValueError(
            f"p_off has {p_off.shape} cells per row, surface has {values.shape[0]} cells"
        )

    total = values.sum()
    if total == 0:
        return np.full(p_off.shape[0], np.nan)
    return (p_off * values[None, :]).sum(axis=1) / total
