"""The entry's public functions are importable from the package root."""

import scbasket
from scbasket import drive_kinds, help_table, rotation_table


def test_entry_functions_are_exported() -> None:
    assert (help_table.__module__, drive_kinds.__module__, rotation_table.__module__) == (
        "scbasket.wind", "scbasket.help_kinds", "scbasket.rotation")
    assert {"help_table", "drive_kinds", "rotation_table"} <= set(scbasket.__all__)
