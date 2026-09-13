"""Ingesta y perfil de calidad del open data de baloncesto de SkillCorner."""

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
