"""Tracking-data measures on SkillCorner's open basketball data.

The entry, "Nobody helps the helper": when a defender leaves his man to stop a drive, does
anyone move toward the man left? Its modules are `wind` (`help_table`: the drives and the
helper's step), `help_kinds` (`drive_kinds`: near and long help) and `rotation`
(`rotation_table`: the other three defenders against a placebo). `io` loads the data.

The remaining modules (`epc`, `forward`, `conditional`, `control`, ...) are an earlier study of
rebound approach kinematics, kept under `docs/bounce/`.

A definition, never a detector: it measures vectors, not intentions. See the README.
"""

from scbasket.help_kinds import drive_kinds
from scbasket.io import (
    Dataset,
    iter_frames,
    load_events,
    load_game_data,
    load_tracking,
)
from scbasket.rotation import rotation_table
from scbasket.wind import help_table

__all__ = [
    "Dataset",
    "drive_kinds",
    "help_table",
    "iter_frames",
    "load_events",
    "load_game_data",
    "load_tracking",
    "rotation_table",
]
__version__ = "0.1.0"
