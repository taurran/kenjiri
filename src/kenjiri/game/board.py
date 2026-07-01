"""Playfield (Field) for Kenjiri — pure logic, no pygame.

Matrix per D25: columns 1-10 left-to-right, rows 1-22 bottom-up. Rows 1-20
are visible; rows 21-22 are the hidden Buffer (cells exist, render nothing).
A cell is ``(col, row)``.
"""
from __future__ import annotations

from typing import Iterable

from .pieces import Cell, PieceKind

COLS = 10
"""Number of columns (1-10)."""

ROWS = 22
"""Total rows including the Buffer (1-22)."""

VISIBLE_ROWS = 20
"""Rows 1-20 render; rows 21-22 are the hidden Buffer (D25)."""


class Board:
    """The 10x22 Field, backed by a sparse ``dict[(col, row) -> PieceKind]``.

    Provides collision queries, locking, full-row detection and row clearing
    with downward collapse. Buffer rows (21-22) behave exactly like visible
    rows (D25) — they can hold cells and be cleared.
    """

    def __init__(self) -> None:
        """Create an empty Field."""
        self._cells: dict[Cell, PieceKind] = {}

    @staticmethod
    def in_bounds(col: int, row: int) -> bool:
        """Return True when ``(col, row)`` lies inside the 10x22 matrix."""
        return 1 <= col <= COLS and 1 <= row <= ROWS

    def collides(self, cells: Iterable[Cell]) -> bool:
        """Return True if any cell is occupied or outside columns 1-10 /
        rows 1-22 (the contract's out-of-bounds rule)."""
        for col, row in cells:
            if not self.in_bounds(col, row) or (col, row) in self._cells:
                return True
        return False

    def lock(self, cells: Iterable[Cell], kind: PieceKind) -> None:
        """Fix ``cells`` into the Field as blocks of ``kind``.

        Raises ``ValueError`` if any cell is out of bounds — locking outside
        the matrix is always a logic bug upstream.
        """
        cell_list = list(cells)
        for col, row in cell_list:
            if not self.in_bounds(col, row):
                raise ValueError(f"cannot lock out-of-bounds cell ({col}, {row})")
        for cell in cell_list:
            self._cells[cell] = kind

    def cell(self, col: int, row: int) -> PieceKind | None:
        """Return the kind occupying ``(col, row)``, or None when empty."""
        return self._cells.get((col, row))

    def full_rows(self) -> list[int]:
        """Return the sorted list of rows in which every column is occupied.

        Buffer rows (21-22) are eligible like any others (D25).
        """
        counts: dict[int, int] = {}
        for _, row in self._cells:
            counts[row] = counts.get(row, 0) + 1
        return sorted(row for row, n in counts.items() if n == COLS)

    def clear_rows(self, rows: Iterable[int]) -> None:
        """Remove ``rows`` and collapse everything above them downward.

        Each surviving cell drops by the number of cleared rows below it.
        """
        cleared = set(rows)
        if not cleared:
            return
        collapsed: dict[Cell, PieceKind] = {}
        for (col, row), kind in self._cells.items():
            if row in cleared:
                continue
            drop = sum(1 for r in cleared if r < row)
            collapsed[(col, row - drop)] = kind
        self._cells = collapsed
