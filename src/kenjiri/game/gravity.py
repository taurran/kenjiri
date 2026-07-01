"""Gravity curve for Kenjiri (D6) — pure logic, no pygame.

D6 verbatim: ``framesPerRow(level) = max(48 − 3·level, 4)`` at a 60 fps
reference; level advances every 10 lines, unbounded, speed capped at the
4-frame floor. Fractional-row progress is handled by the integer gravity
accumulator in :mod:`kenjiri.game.state` (accumulate 1 unit per frame, fall
when the accumulator reaches ``frames_per_row``) — exact, no float drift.
"""
from __future__ import annotations

BASE_FRAMES = 48
"""Frames per row at level 0 (0.8 s/row at 60 fps)."""

RAMP_FRAMES_PER_LEVEL = 3
"""Linear speed-up per level (D6 — the linear ramp, not the NES cliff)."""

FLOOR_FRAMES = 4
"""Minimum frames per row — reached at level 15 and held forever."""

LINES_PER_LEVEL = 10
"""Level advances every 10 lines (D6)."""

SOFT_DROP_FACTOR = 20
"""Soft drop multiplies gravity 20x, capped at 1 row/frame (D5)."""


def frames_per_row(level: int) -> int:
    """Return gravity as frames-per-row at ``level`` (D6 verbatim).

    ``max(48 - 3*level, 4)``: L0=48, L8=24, L14=6, L15+=4.
    """
    if level < 0:
        raise ValueError(f"level must be non-negative, got {level}")
    return max(BASE_FRAMES - RAMP_FRAMES_PER_LEVEL * level, FLOOR_FRAMES)


def soft_drop_units_per_frame(level: int) -> int:
    """Return the gravity-accumulator units added per frame of held soft
    drop: 20x gravity, capped at 1 row/frame (D5).

    One row falls per ``frames_per_row(level)`` accumulated units, so the
    cap is expressed exactly as ``min(20, frames_per_row(level))``.
    """
    return min(SOFT_DROP_FACTOR, frames_per_row(level))


def level_for_lines(lines: int) -> int:
    """Return the level for a total cleared-line count (D6: every 10 lines,
    unbounded)."""
    if lines < 0:
        raise ValueError(f"lines must be non-negative, got {lines}")
    return lines // LINES_PER_LEVEL
