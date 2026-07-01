"""Piece data and SRS rotation for Kenjiri.

Pure data module — no pygame. Coordinates follow D25: columns 1-10
left-to-right, rows 1-22 bottom-up (rows 21-22 = hidden Buffer); a cell is
``(col, row)``, so within this module every offset ``(dx, dy)`` has ``+dy``
pointing UP. The published SRS kick tables already use +y-up, so they appear
verbatim below.

Spawn placement per D27 (verbatim): "I spawns in row 21 (its single row);
O occupies columns 5-6, rows 21-22; all other pieces occupy columns 4-6,
rows 21-22 (flat-side down)".

Rotation states are indexed 0=spawn, 1=R (one CW), 2=180, 3=L (one CCW).
States 1-3 are derived from the spawn state by true SRS rotation inside each
piece's bounding box (3x3 for J/L/S/T/Z, 4x4 for I, 2x2 for O). O's four
state entries are therefore identical — it has a single distinct shape and
never kicks.
"""
from __future__ import annotations

import typing
from typing import Literal

PieceKind = Literal["I", "O", "T", "S", "Z", "J", "L"]

Cell = tuple[int, int]
"""A ``(col, row)`` matrix cell or a ``(dx, dy)`` offset, +dy up."""

PIECE_KINDS: tuple[PieceKind, ...] = typing.get_args(PieceKind)

_BOX_SIZE: dict[PieceKind, int] = {
    "I": 4, "O": 2, "T": 3, "S": 3, "Z": 3, "J": 3, "L": 3,
}

# Spawn-state (index 0) offsets from the piece origin (bounding-box
# bottom-left corner), y-up. Chosen so spawn_origin() + offsets reproduces
# the D27 spawn cells exactly.
_SPAWN_OFFSETS: dict[PieceKind, frozenset[Cell]] = {
    "I": frozenset({(0, 2), (1, 2), (2, 2), (3, 2)}),
    "O": frozenset({(0, 0), (1, 0), (0, 1), (1, 1)}),
    "T": frozenset({(0, 1), (1, 1), (2, 1), (1, 2)}),
    "S": frozenset({(0, 1), (1, 1), (1, 2), (2, 2)}),
    "Z": frozenset({(0, 2), (1, 2), (1, 1), (2, 1)}),
    "J": frozenset({(0, 2), (0, 1), (1, 1), (2, 1)}),
    "L": frozenset({(2, 2), (0, 1), (1, 1), (2, 1)}),
}

# Piece origin (bounding-box bottom-left, absolute matrix cell) at spawn.
_SPAWN_ORIGIN: dict[PieceKind, Cell] = {
    "I": (4, 19),
    "O": (5, 21),
    "T": (4, 20),
    "S": (4, 20),
    "Z": (4, 20),
    "J": (4, 20),
    "L": (4, 20),
}


def _rotate_cw(cells: frozenset[Cell], box: int) -> frozenset[Cell]:
    """Rotate offsets 90 degrees clockwise inside a ``box`` x ``box`` grid.

    In y-up coordinates a CW quarter turn maps ``(x, y) -> (y, box-1-x)``.
    """
    return frozenset((y, box - 1 - x) for x, y in cells)


def _build_states(kind: PieceKind) -> tuple[frozenset[Cell], ...]:
    """Derive the 4 SRS rotation states (0=spawn, 1=R, 2=180, 3=L)."""
    states = [_SPAWN_OFFSETS[kind]]
    for _ in range(3):
        states.append(_rotate_cw(states[-1], _BOX_SIZE[kind]))
    return tuple(states)


CELLS: dict[PieceKind, tuple[frozenset[Cell], ...]] = {
    kind: _build_states(kind) for kind in PIECE_KINDS
}
"""4 rotation states per kind (index 0 = spawn), cells as origin offsets."""


def spawn_origin(kind: PieceKind) -> Cell:
    """Return the absolute ``(col, row)`` piece origin at spawn.

    Adding ``CELLS[kind][0]`` offsets to this origin yields the D27 spawn
    cells: I -> {(4,21)..(7,21)}, O -> columns 5-6 rows 21-22, all others ->
    columns 4-6 rows 21-22 flat-side down.
    """
    return _SPAWN_ORIGIN[kind]


def spawn_cells(kind: PieceKind) -> frozenset[Cell]:
    """Return the absolute matrix cells ``kind`` occupies at spawn (D27)."""
    ox, oy = _SPAWN_ORIGIN[kind]
    return frozenset((ox + dx, oy + dy) for dx, dy in CELLS[kind][0])


def rotated(kind: PieceKind, state: int, direction: int) -> int:
    """Return the next rotation state index.

    ``direction`` is ``+1`` for clockwise, ``-1`` for counter-clockwise.
    ``state`` must be a valid index into ``CELLS[kind]`` (0-3).
    """
    if direction not in (1, -1):
        raise ValueError(f"direction must be +1 (CW) or -1 (CCW), got {direction!r}")
    if not 0 <= state < len(CELLS[kind]):
        raise ValueError(f"invalid rotation state {state!r} for {kind!r}")
    return (state + direction) % len(CELLS[kind])


_KickTable = dict[tuple[int, int], tuple[Cell, ...]]

# Standard SRS wall-kick offset tables, keyed by (from_state, to_state) with
# states 0=spawn, 1=R, 2=180, 3=L. Offsets are (dx, dy) with +dy UP, applied
# in order; the first non-colliding placement wins. Values are the published
# guideline SRS tables verbatim (they use the same y-up convention as D25).
_JLSTZ_KICKS: _KickTable = {
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}

_I_KICKS: _KickTable = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}

KICKS: dict[str, _KickTable] = {
    "JLSTZ": _JLSTZ_KICKS,
    "I": _I_KICKS,
}
"""SRS wall-kick offset tables: the shared JLSTZ table plus the I table.

O never kicks — use :func:`kick_offsets` for uniform per-kind dispatch.
"""

_NO_KICK: tuple[Cell, ...] = ((0, 0),)


def kick_offsets(kind: PieceKind, from_state: int, to_state: int) -> tuple[Cell, ...]:
    """Return the ordered SRS kick offsets for a ``from_state -> to_state``
    rotation of ``kind``.

    Dispatches to the I table for I, the shared JLSTZ table for J/L/S/T/Z,
    and a lone ``(0, 0)`` for O (O never kicks — its rotation is only ever
    attempted in place).
    """
    if kind == "O":
        return _NO_KICK
    table = _I_KICKS if kind == "I" else _JLSTZ_KICKS
    return table[(from_state, to_state)]
