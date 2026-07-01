"""Tests for kenjiri.game.pieces — piece data, spawn placement (D27), SRS kicks.

Matrix convention (D25): columns 1-10 left-to-right, rows 1-22 bottom-up,
rows 21-22 hidden Buffer. A cell is ``(col, row)``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from kenjiri.game.pieces import (
    CELLS,
    KICKS,
    PIECE_KINDS,
    kick_offsets,
    rotated,
    spawn_cells,
    spawn_origin,
)

Cell = tuple[int, int]

COL_MIN, COL_MAX = 1, 10
ROW_MIN, ROW_MAX = 1, 22


def in_bounds(cells: frozenset[Cell]) -> bool:
    """True when every cell lies inside columns 1-10 / rows 1-22 (D25)."""
    return all(COL_MIN <= c <= COL_MAX and ROW_MIN <= r <= ROW_MAX for c, r in cells)


def place(kind: str, state: int, origin: Cell) -> frozenset[Cell]:
    """Absolute cells for ``kind`` in ``state`` with its origin at ``origin``."""
    ox, oy = origin
    return frozenset((ox + dx, oy + dy) for dx, dy in CELLS[kind][state])


def resolve_rotation(
    kind: str,
    state: int,
    direction: int,
    origin: Cell,
    occupied: frozenset[Cell] = frozenset(),
) -> tuple[int, Cell, Cell] | None:
    """Minimal SRS resolution: try kick offsets in order, first legal wins.

    Returns ``(new_state, new_origin, chosen_kick)`` or ``None`` if every
    kick fails. Legality = in bounds and not overlapping ``occupied``.
    """
    new_state = rotated(kind, state, direction)
    for dx, dy in kick_offsets(kind, state, new_state):
        ox, oy = origin
        candidate = (ox + dx, oy + dy)
        cells = place(kind, new_state, candidate)
        if in_bounds(cells) and not (cells & occupied):
            return new_state, candidate, (dx, dy)
    return None


# ---------------------------------------------------------------- piece data


def test_all_seven_kinds_present() -> None:
    assert set(PIECE_KINDS) == {"I", "O", "T", "S", "Z", "J", "L"}
    assert set(CELLS) == set(PIECE_KINDS)


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_four_rotation_states_of_four_cells(kind: str) -> None:
    states = CELLS[kind]
    assert len(states) == 4
    for state_cells in states:
        assert len(state_cells) == 4


def test_o_rotation_states_identical() -> None:
    """O has a single distinct shape — all 4 state entries are equal."""
    assert len(set(CELLS["O"])) == 1


# ------------------------------------------------------------ spawn per D27


def test_i_spawn_cells_exact() -> None:
    assert spawn_cells("I") == frozenset({(4, 21), (5, 21), (6, 21), (7, 21)})


def test_o_spawn_cells_exact() -> None:
    assert spawn_cells("O") == frozenset({(5, 21), (6, 21), (5, 22), (6, 22)})


def test_t_spawn_flat_side_down() -> None:
    """T: flat row on row 21 across columns 4-6, nub above at (5, 22)."""
    assert spawn_cells("T") == frozenset({(4, 21), (5, 21), (6, 21), (5, 22)})


@pytest.mark.parametrize("kind", ["J", "L", "S", "Z"])
def test_jlsz_spawn_columns_and_rows(kind: str) -> None:
    """Non-I/O pieces occupy columns 4-6, rows 21-22, flat-side down (D27)."""
    cells = spawn_cells(kind)
    assert {c for c, _ in cells} <= {4, 5, 6}
    assert {r for _, r in cells} == {21, 22}


@pytest.mark.parametrize("kind", ["J", "L"])
def test_jl_three_wide_bottom_row(kind: str) -> None:
    """J/L flat-side down: full 3-cell bar on row 21."""
    bottom = {c for c, r in spawn_cells(kind) if r == 21}
    assert bottom == {4, 5, 6}


def test_spawn_origin_reconstructs_spawn_cells() -> None:
    for kind in PIECE_KINDS:
        assert place(kind, 0, spawn_origin(kind)) == spawn_cells(kind)


# ------------------------------------------------------------------ rotated


def test_rotated_cycles_cw_and_ccw() -> None:
    assert rotated("T", 0, 1) == 1
    assert rotated("T", 3, 1) == 0
    assert rotated("T", 0, -1) == 3
    assert rotated("T", 2, -1) == 1


# ---------------------------------------------------------------- SRS kicks


def test_jlstz_kick_table_exact_0_to_1() -> None:
    assert KICKS["JLSTZ"][(0, 1)] == ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2))


def test_jlstz_kick_table_exact_1_to_0() -> None:
    assert KICKS["JLSTZ"][(1, 0)] == ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2))


def test_i_kick_table_exact_0_to_1() -> None:
    assert KICKS["I"][(0, 1)] == ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2))


def test_kick_tables_cover_all_adjacent_transitions() -> None:
    expected = {(a, b) for a in range(4) for b in ((a + 1) % 4, (a - 1) % 4)}
    assert set(KICKS["JLSTZ"]) == expected
    assert set(KICKS["I"]) == expected


def test_o_never_kicks() -> None:
    """O rotation is only ever attempted in place — single (0,0) offset."""
    for state in range(4):
        for direction in (1, -1):
            offsets = kick_offsets("O", state, rotated("O", state, direction))
            assert offsets == ((0, 0),)


def test_t_wall_kick_left_wall() -> None:
    """T hugging the left wall, state 1 -> 0: (0,0) is out of bounds, the
    JLSTZ table's (+1, 0) wall kick must be chosen."""
    origin = (0, 5)  # box columns 0-2; state-1 cells sit in columns 1-2
    assert in_bounds(place("T", 1, origin))
    result = resolve_rotation("T", 1, -1, origin)
    assert result is not None
    new_state, new_origin, kick = result
    assert new_state == 0
    assert kick == (1, 0)
    assert new_origin == (1, 5)
    assert in_bounds(place("T", new_state, new_origin))


def test_t_floor_kick_upward() -> None:
    """T on the floor, state 3 -> 2 (CCW) with (0,0) and (-1,0) blocked by
    garbage and (-1,-1) blocked by the floor: the upward (0,+2) floor kick
    from the JLSTZ table must be chosen."""
    origin = (4, 1)  # state-3 column occupies rows 1-3 at column 5
    occupied = frozenset({(6, 2), (4, 1)})
    assert in_bounds(place("T", 3, origin))
    assert not (place("T", 3, origin) & occupied)
    result = resolve_rotation("T", 3, -1, origin, occupied)
    assert result is not None
    new_state, new_origin, kick = result
    assert new_state == 2
    assert kick == (0, 2)
    assert new_origin == (4, 3)
    cells = place("T", new_state, new_origin)
    assert in_bounds(cells)
    assert not (cells & occupied)


def test_i_wall_kick_right_wall_uses_i_table() -> None:
    """Vertical I at the right wall, state 1 -> 0: (0,0) and (+2,0) leave the
    field, the I table's (-1, 0) kick must be chosen."""
    origin = (8, 5)  # state-1 cells occupy column 10
    assert in_bounds(place("I", 1, origin))
    result = resolve_rotation("I", 1, -1, origin)
    assert result is not None
    new_state, new_origin, kick = result
    assert new_state == 0
    assert kick == (-1, 0)
    assert in_bounds(place("I", new_state, new_origin))


# ------------------------------------------------------- negative assertions


def test_spawn_cells_always_in_bounds() -> None:
    """Negative: no legal spawn places cells outside cols 1-10 / rows 1-22."""
    for kind in PIECE_KINDS:
        cells = spawn_cells(kind)
        assert in_bounds(cells), f"{kind} spawn out of bounds: {cells}"
        assert {r for _, r in cells} <= {21, 22}


def test_kick_resolution_from_spawn_always_in_bounds() -> None:
    """Negative: every rotation resolved via kicks from the spawn position on
    an empty field lands fully inside the 10x22 matrix."""
    for kind in PIECE_KINDS:
        for direction in (1, -1):
            state, origin = 0, spawn_origin(kind)
            for _ in range(4):  # full rotation cycle
                result = resolve_rotation(kind, state, direction, origin)
                assert result is not None, f"{kind} rotation failed at spawn"
                state, origin, _kick = result
                assert in_bounds(place(kind, state, origin)), (
                    f"{kind} state {state} out of bounds at {origin}"
                )
