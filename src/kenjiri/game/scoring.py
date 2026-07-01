"""Scoring for Kenjiri (D7) — pure logic, no pygame.

D7 verbatim: "Single 40 · Double 100 · Triple 300 · Kenjiri (4 lines) 1200,
each × (level + 1). Soft drop +1/row while held; hard drop +2/row dropped."
Edge (D7): "Score awarded at lock using level before any level-up from that
clear." Score display caps at 9,999,999 (D7/D26); internal line count is
unbounded (D26) — clamping the LINES display is the UI's job.
"""
from __future__ import annotations

CLEAR_POINTS: dict[int, int] = {1: 40, 2: 100, 3: 300, 4: 1200}
"""Base points by simultaneous lines cleared (D7): Single/Double/Triple/Kenjiri."""

SOFT_DROP_POINTS_PER_ROW = 1
"""+1 point per row descended while soft drop is held (D7)."""

HARD_DROP_POINTS_PER_ROW = 2
"""+2 points per row dropped by a hard drop (D7)."""

SCORE_CAP = 9_999_999
"""Score caps at 9,999,999 without overflow (D7)."""


def clear_points(rows: int, level: int) -> int:
    """Return points for clearing ``rows`` simultaneous lines at ``level``.

    Per D7: base points (40/100/300/1200) × (level + 1). ``level`` must be
    the level *before* any level-up caused by this clear (D7 edge).
    """
    if rows not in CLEAR_POINTS:
        raise ValueError(f"a lock clears 1-4 rows, got {rows}")
    if level < 0:
        raise ValueError(f"level must be non-negative, got {level}")
    return CLEAR_POINTS[rows] * (level + 1)


def capped(score: int) -> int:
    """Return ``score`` clamped to the 9,999,999 display/property cap (D7)."""
    return min(score, SCORE_CAP)
