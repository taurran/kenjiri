"""Tests for kenjiri.game.scoring (D7)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from kenjiri.game import scoring


class TestClearPoints:
    """D7: Single 40 · Double 100 · Triple 300 · Kenjiri 1200, x (level+1)."""

    @pytest.mark.parametrize(
        ("rows", "base"), [(1, 40), (2, 100), (3, 300), (4, 1200)]
    )
    def test_base_table_at_level_0(self, rows: int, base: int) -> None:
        assert scoring.clear_points(rows, 0) == base

    def test_level_multiplier(self) -> None:
        assert scoring.clear_points(1, 9) == 40 * 10
        assert scoring.clear_points(3, 4) == 300 * 5

    def test_kenjiri_at_level_2_is_3600(self) -> None:
        # Acceptance spot check: 1200 x (2 + 1).
        assert scoring.clear_points(4, 2) == 3600

    @pytest.mark.parametrize("rows", [0, 5, -1])
    def test_invalid_row_count_rejected(self, rows: int) -> None:
        with pytest.raises(ValueError):
            scoring.clear_points(rows, 0)

    def test_negative_level_rejected(self) -> None:
        with pytest.raises(ValueError):
            scoring.clear_points(1, -1)


class TestDropPoints:
    """D7: soft drop +1/row while held; hard drop +2/row dropped."""

    def test_constants(self) -> None:
        assert scoring.SOFT_DROP_POINTS_PER_ROW == 1
        assert scoring.HARD_DROP_POINTS_PER_ROW == 2


class TestCap:
    """D7: score caps at 9,999,999."""

    def test_below_cap_passes_through(self) -> None:
        assert scoring.capped(123456) == 123456

    def test_at_and_above_cap_clamps(self) -> None:
        assert scoring.capped(9_999_999) == 9_999_999
        assert scoring.capped(10_000_000) == 9_999_999
        assert scoring.capped(999_999_999) == 9_999_999
