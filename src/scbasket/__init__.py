"""Rebound approach kinematics on SkillCorner's open basketball tracking.

A definition, never a detector: it measures vectors, not intentions. See the README.
"""

from scbasket.io import (
    Dataset,
    iter_frames,
    load_events,
    load_game_data,
    load_tracking,
)

__all__ = [
    "Dataset",
    "iter_frames",
    "load_events",
    "load_game_data",
    "load_tracking",
]
__version__ = "0.1.0"
