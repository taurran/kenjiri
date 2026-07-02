"""Tests for kenjiri.game.board (Field, D25)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from kenjiri.game.board import COLS, ROWS, VISIBLE_ROWS, Board


def fill_row(board: Board, row: int, cols: range = range(1, 11)) -> None:
    """Lock single cells across ``cols`` of ``row``."""
    board.lock([(col, row) for col in cols], "O")


class TestGeometry:
    def test_dimensions(self) -> None:
        assert COLS == 10
        assert ROWS == 22
        assert VISIBLE_ROWS == 20

    @pytest.mark.parametrize(
        "cell", [(0, 1), (11, 1), (1, 0), (1, 23), (-3, 5), (5, -1)]
    )
    def test_out_of_bounds_collides(self, cell: tuple[int, int]) -> None:
        assert Board().collides([cell])

    @pytest.mark.parametrize("cell", [(1, 1), (10, 1), (1, 22), (10, 22), (5, 21)])
    def test_in_bounds_empty_does_not_collide(self, cell: tuple[int, int]) -> None:
        assert not Board().collides([cell])


class TestLockAndCollide:
    def test_lock_sets_cells(self) -> None:
        board = Board()
        board.lock([(3, 1), (4, 1)], "T")
        assert board.cell(3, 1) == "T"
        assert board.cell(4, 1) == "T"
        assert board.cell(5, 1) is None

    def test_occupied_cell_collides(self) -> None:
        board = Board()
        board.lock([(5, 5)], "I")
        assert board.collides([(5, 5)])
        assert not board.collides([(5, 6)])

    def test_lock_out_of_bounds_raises(self) -> None:
        with pytest.raises(ValueError):
            Board().lock([(11, 1)], "I")


class TestFullRows:
    def test_empty_board_has_no_full_rows(self) -> None:
        assert Board().full_rows() == []

    def test_partial_row_not_full(self) -> None:
        board = Board()
        fill_row(board, 1, range(1, 10))  # 9 of 10 columns
        assert board.full_rows() == []

    def test_full_rows_sorted(self) -> None:
        board = Board()
        fill_row(board, 3)
        fill_row(board, 1)
        assert board.full_rows() == [1, 3]

    def test_buffer_row_can_be_full(self) -> None:
        # D25: a line clear in a Buffer row is possible.
        board = Board()
        fill_row(board, 21)
        assert board.full_rows() == [21]


class TestClearRows:
    def test_clear_single_row_collapses_above(self) -> None:
        board = Board()
        fill_row(board, 1)
        board.lock([(4, 2), (7, 3)], "S")
        board.clear_rows([1])
        assert board.full_rows() == []
        assert board.cell(4, 1) == "S"
        assert board.cell(7, 2) == "S"
        assert board.cell(4, 2) is None

    def test_clear_multiple_nonadjacent_rows(self) -> None:
        board = Board()
        fill_row(board, 1)
        fill_row(board, 3)
        board.lock([(2, 2)], "Z")   # between cleared rows: drops 1
        board.lock([(9, 5)], "L")   # above both: drops 2
        board.clear_rows([1, 3])
        assert board.cell(2, 1) == "Z"
        assert board.cell(9, 3) == "L"
        assert board.cell(2, 2) is None
        assert board.cell(9, 5) is None

    def test_clear_buffer_row_collapses_row_22(self) -> None:
        board = Board()
        fill_row(board, 21)
        board.lock([(6, 22)], "J")
        board.clear_rows([21])
        assert board.cell(6, 21) == "J"
        assert board.cell(6, 22) is None

    def test_clear_no_rows_is_noop(self) -> None:
        board = Board()
        board.lock([(1, 1)], "I")
        board.clear_rows([])
        assert board.cell(1, 1) == "I"
