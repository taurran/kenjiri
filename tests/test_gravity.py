"""Tests for kenjiri.game.gravity (D6)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from kenjiri.game import gravity


class TestFramesPerRow:
    """D6 verbatim: framesPerRow(level) = max(48 - 3*level, 4)."""

    @pytest.mark.parametrize(
        ("level", "expected"),
        [(0, 48), (1, 45), (8, 24), (14, 6), (15, 4), (16, 4), (100, 4)],
    )
    def test_spot_checks(self, level: int, expected: int) -> None:
        assert gravity.frames_per_row(level) == expected

    def test_monotonic_until_floor(self) -> None:
        values = [gravity.frames_per_row(lvl) for lvl in range(20)]
        assert values == sorted(values, reverse=True)
        assert min(values) == gravity.FLOOR_FRAMES == 4

    def test_negative_level_rejected(self) -> None:
        with pytest.raises(ValueError):
            gravity.frames_per_row(-1)


class TestSoftDrop:
    """D5: soft drop = 20x gravity, capped at 1 row/frame."""

    def test_soft_drop_units_level_0(self) -> None:
        # 20 units/frame against 48 units/row: 20x speed, below the cap.
        assert gravity.soft_drop_units_per_frame(0) == 20

    def test_soft_drop_capped_at_one_row_per_frame_at_floor(self) -> None:
        # At the 4-frame floor, 20x would exceed 1 row/frame: capped exactly.
        assert gravity.soft_drop_units_per_frame(15) == 4
        assert gravity.soft_drop_units_per_frame(99) == 4


class TestLevelForLines:
    """D6: level advances every 10 lines, unbounded."""

    @pytest.mark.parametrize(
        ("lines", "level"),
        [(0, 0), (9, 0), (10, 1), (11, 1), (99, 9), (100, 10), (12345, 1234)],
    )
    def test_level_progression(self, lines: int, level: int) -> None:
        assert gravity.level_for_lines(lines) == level

    def test_negative_lines_rejected(self) -> None:
        with pytest.raises(ValueError):
            gravity.level_for_lines(-1)
