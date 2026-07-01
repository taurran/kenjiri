"""Kenjiri authoritative game state machine — pure logic, no pygame.

``Game.step(inputs)`` advances EXACTLY one 60 fps reference logic frame and
returns the ordered list of :class:`GameEvent` emitted that frame. The
UI/audio layer consumes events; game logic never imports UI/audio.

Ledger constants implemented verbatim:

- Gravity D6: ``framesPerRow(level) = max(48 − 3·level, 4)``; level advances
  every 10 lines; integer fractional-row accumulator.
- Scoring D7: clear table × (level + 1), awarded at lock using the level
  *before* any level-up from that clear; soft drop +1/row held; hard drop
  +2/row dropped; score property caps at 9,999,999 (lines unbounded, D26).
- Spawn D25/D27: guideline spawn cells; on the spawn frame, if the cell
  below is free the piece immediately falls one row; block-out is checked at
  the spawn position BEFORE this drop.
- Top-out D25: block-out (spawning piece overlaps a block) OR lock-out
  (piece locks with ALL cells above row 20). Partially-above locks are legal
  and their Buffer cells persist and clear normally.
- Lock delay D18: 0.5 s (30 frames); any successful move/rotate while
  grounded resets it, max 15 resets per piece, then force-lock on next
  ground contact; hard drop locks instantly; the reset counter clears when
  the piece falls to a new lowest row; soft drop onto ground does NOT skip
  the delay.
- DAS/ARR D5/D26/D27: DAS 10 frames, ARR 2 frames; direction change mid-DAS
  resets the charge; charge held through hard drop into the next spawn;
  charge keeps accruing during the line-clear animation, capped at full.
- Clear animation D23/D26: 18 frames; input EVENTS ignored during it (held
  DAS accrues); no ARE — after collapse (and after any non-clearing lock)
  the next piece spawns on the next logic frame.
- Hold D3/D19: once per piece, re-enabled at next lock; first hold stashes
  and spawns the next bag piece; later holds swap.
- Ghost D25: active piece dropped to rest; None while the falling piece is
  entirely in the Buffer (rows 21-22).
- piece_counts D8: increments once per piece at its (bag) spawn — a
  held-then-swapped piece is counted once, at its original spawn.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto

from . import gravity, pieces, scoring
from .bag import SevenBag
from .board import VISIBLE_ROWS, Board
from .inputmap import InputFrame
from .pieces import Cell, PieceKind

LOCK_DELAY_FRAMES = 30
"""0.5 s lock delay at 60 fps (D18)."""

MAX_LOCK_RESETS = 15
"""Maximum grounded move/rotate lock-delay resets per piece (D18)."""

CLEAR_ANIMATION_FRAMES = 18
"""Line-clear animation length, ~0.3 s (D23)."""

DAS_FRAMES = 10
"""Delayed auto-shift initial delay, 167 ms (D5)."""

ARR_FRAMES = 2
"""Auto-repeat rate, 33 ms (D5)."""


class GameEvent(Enum):
    """Events emitted by :meth:`Game.step`, consumed by the UI/audio layer."""

    LOCK = auto()
    HARD_DROP = auto()
    CLEAR_SINGLE = auto()
    CLEAR_DOUBLE = auto()
    CLEAR_TRIPLE = auto()
    CLEAR_KENJIRI = auto()
    LEVEL_UP = auto()
    TOP_OUT = auto()
    HOLD_USED = auto()
    SPAWN = auto()


_CLEAR_EVENTS: dict[int, GameEvent] = {
    1: GameEvent.CLEAR_SINGLE,
    2: GameEvent.CLEAR_DOUBLE,
    3: GameEvent.CLEAR_TRIPLE,
    4: GameEvent.CLEAR_KENJIRI,
}


@dataclass(frozen=True)
class ActivePiece:
    """Read-only view of the falling piece: kind, absolute cells, and ghost
    cells (None while the piece is entirely in the Buffer, D25)."""

    kind: PieceKind
    cells: frozenset[Cell]
    ghost_cells: frozenset[Cell] | None


def _piece_cells(kind: PieceKind, rot: int, origin: Cell) -> frozenset[Cell]:
    """Return the absolute matrix cells for ``kind`` at rotation state
    ``rot`` with the piece origin at ``origin``."""
    ox, oy = origin
    return frozenset((ox + dx, oy + dy) for dx, dy in pieces.CELLS[kind][rot])


class Game:
    """The full Kenjiri rules state machine (see module docstring).

    Construct with an injected ``random.Random`` (seed it for reproducible
    piece sequences); drive with :meth:`step` once per logic frame.
    """

    def __init__(self, rng: random.Random) -> None:
        """Create a new game at level 0 with an empty Field.

        The first piece spawns on the first :meth:`step` call.
        """
        self._board = Board()
        self._bag = SevenBag(rng)
        self._score_raw = 0
        self._lines = 0
        self._piece_counts: dict[PieceKind, int] = {k: 0 for k in pieces.PIECE_KINDS}
        self._hold_kind: PieceKind | None = None
        self._hold_available = True
        self._over = False
        self._clearing: list[int] | None = None
        self._clear_frames_left = 0
        self._spawn_pending = True
        # Active piece (valid only when _kind is not None).
        self._kind: PieceKind | None = None
        self._rot = 0
        self._origin: Cell = (0, 0)
        # Per-piece timers/counters.
        self._grav_acc = 0  # integer units; falls when acc >= frames_per_row
        self._lock_timer = 0
        self._lock_resets = 0
        self._lowest_row = 0
        self._was_grounded = False
        # DAS state (persists across pieces per D5/D26/D27).
        self._das_dir = 0  # -1 left, +1 right, 0 none
        self._das_charge = 0

    # ------------------------------------------------------------------
    # Read-only properties (contract)
    # ------------------------------------------------------------------

    @property
    def board(self) -> Board:
        """The Field."""
        return self._board

    @property
    def active(self) -> ActivePiece | None:
        """The falling piece view, or None between lock and the next spawn
        (including during the clear animation and after game over)."""
        if self._kind is None:
            return None
        cells = self._cells()
        return ActivePiece(self._kind, cells, self._ghost_cells(cells))

    @property
    def hold_kind(self) -> PieceKind | None:
        """The stashed piece kind, or None before the first hold."""
        return self._hold_kind

    @property
    def hold_available(self) -> bool:
        """True when hold may be used (once per piece, D3/D19)."""
        return self._hold_available

    @property
    def next_kind(self) -> PieceKind:
        """The next piece kind the Bag will deal (1-piece NEXT preview)."""
        return self._bag.peek(1)[0]

    @property
    def score(self) -> int:
        """Current score, capped at 9,999,999 (D7)."""
        return scoring.capped(self._score_raw)

    @property
    def lines(self) -> int:
        """Total lines cleared — raw and unbounded (D26); display clamping
        is the UI's job."""
        return self._lines

    @property
    def level(self) -> int:
        """Current level: advances every 10 lines, unbounded (D6)."""
        return gravity.level_for_lines(self._lines)

    @property
    def piece_counts(self) -> dict[PieceKind, int]:
        """Spawn counters per kind (D8) — each piece counted once, at its
        bag spawn (a swapped-in held piece is not re-counted)."""
        return dict(self._piece_counts)

    @property
    def over(self) -> bool:
        """True after a top-out (block-out or lock-out, D25)."""
        return self._over

    @property
    def clearing(self) -> list[int] | None:
        """Rows mid-clear-animation, or None when no animation is running."""
        return list(self._clearing) if self._clearing is not None else None

    # ------------------------------------------------------------------
    # Frame step
    # ------------------------------------------------------------------

    def step(self, inputs: InputFrame) -> list[GameEvent]:
        """Advance exactly one logic frame; return the events it emitted."""
        events: list[GameEvent] = []
        if self._over:
            return events

        # --- Clear animation: input EVENTS ignored, DAS accrues (D27) ---
        if self._clearing is not None:
            self._das_accrue_only(inputs)
            self._clear_frames_left -= 1
            if self._clear_frames_left <= 0:
                self._board.clear_rows(self._clearing)
                self._clearing = None
                # No additional ARE: next piece spawns on the NEXT frame (D26).
                self._spawn_pending = True
            return events

        # --- Spawn (the frame after a lock / collapse, D26) ---
        if self._spawn_pending:
            self._spawn_pending = False
            self._spawn_from_bag(events)
            if self._over:
                return events

        # --- Input phase (hold → rotate → shift → hard drop) ---
        if inputs.hold_pressed and self._hold_available:
            self._do_hold(events)
            if self._over:
                return events

        if inputs.rotate_cw_pressed:
            self._try_rotate(+1)
        if inputs.rotate_ccw_pressed:
            self._try_rotate(-1)

        self._update_das(inputs)

        if inputs.hard_drop_pressed:
            rows = self._drop_to_rest()
            self._score_raw += rows * scoring.HARD_DROP_POINTS_PER_ROW
            events.append(GameEvent.HARD_DROP)
            self._lock_piece(events)  # hard drop locks instantly (D18)
            return events

        # --- Gravity phase (integer accumulator; soft drop D5) ---
        soft = inputs.soft_drop_held
        fpr = gravity.frames_per_row(self.level)
        self._grav_acc += gravity.soft_drop_units_per_frame(self.level) if soft else 1
        while self._grav_acc >= fpr:
            if self._try_move(0, -1):
                self._grav_acc -= fpr
                if soft:
                    self._score_raw += scoring.SOFT_DROP_POINTS_PER_ROW
            else:
                self._grav_acc = 0
                break

        # --- Lock delay (D18) ---
        grounded = self._grounded()
        if grounded:
            newly_grounded = not self._was_grounded
            self._was_grounded = True
            if newly_grounded and self._lock_resets >= MAX_LOCK_RESETS:
                # Resets exhausted: force-lock on next ground contact (D18).
                self._lock_piece(events)
                return events
            self._lock_timer += 1
            if self._lock_timer >= LOCK_DELAY_FRAMES:
                self._lock_piece(events)
                return events
        else:
            self._was_grounded = False
            self._lock_timer = 0
        return events

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cells(self) -> frozenset[Cell]:
        """Absolute cells of the active piece (requires an active piece)."""
        assert self._kind is not None
        return _piece_cells(self._kind, self._rot, self._origin)

    def _grounded(self) -> bool:
        """True when the active piece cannot fall one more row."""
        ox, oy = self._origin
        assert self._kind is not None
        return self._board.collides(_piece_cells(self._kind, self._rot, (ox, oy - 1)))

    def _ghost_cells(self, cells: frozenset[Cell]) -> frozenset[Cell] | None:
        """Ghost = active piece dropped to rest; None while the piece is
        entirely in the Buffer rows 21-22 (D25)."""
        if all(row > VISIBLE_ROWS for _, row in cells):
            return None
        assert self._kind is not None
        ox, oy = self._origin
        drop = 0
        while not self._board.collides(
            _piece_cells(self._kind, self._rot, (ox, oy - drop - 1))
        ):
            drop += 1
        return frozenset((col, row - drop) for col, row in cells)

    def _after_successful_action(self, grounded_before: bool) -> None:
        """Lock-delay bookkeeping after any successful move/rotate/fall.

        Falling to a new lowest row clears the reset counter and timer
        (D18); otherwise a successful action while grounded consumes one of
        the 15 resets and restarts the 0.5 s timer.
        """
        new_min = min(row for _, row in self._cells())
        if new_min < self._lowest_row:
            self._lowest_row = new_min
            self._lock_resets = 0
            self._lock_timer = 0
        elif grounded_before and self._lock_resets < MAX_LOCK_RESETS:
            self._lock_timer = 0
            self._lock_resets += 1

    def _try_move(self, dx: int, dy: int) -> bool:
        """Attempt to shift the active piece; True on success. A move into
        any colliding cell is rejected (the piece never overlaps)."""
        assert self._kind is not None
        ox, oy = self._origin
        candidate = (ox + dx, oy + dy)
        if self._board.collides(_piece_cells(self._kind, self._rot, candidate)):
            return False
        grounded_before = self._grounded()
        self._origin = candidate
        self._after_successful_action(grounded_before)
        return True

    def _try_rotate(self, direction: int) -> bool:
        """Attempt an SRS rotation with wall kicks (T1 tables): the first
        non-colliding kick offset wins. True on success."""
        assert self._kind is not None
        new_rot = pieces.rotated(self._kind, self._rot, direction)
        grounded_before = self._grounded()
        ox, oy = self._origin
        for dx, dy in pieces.kick_offsets(self._kind, self._rot, new_rot):
            candidate = (ox + dx, oy + dy)
            if not self._board.collides(_piece_cells(self._kind, new_rot, candidate)):
                self._rot = new_rot
                self._origin = candidate
                self._after_successful_action(grounded_before)
                return True
        return False

    def _drop_to_rest(self) -> int:
        """Drop the active piece straight down to rest; return rows dropped."""
        rows = 0
        while self._try_move(0, -1):
            rows += 1
        return rows

    # --- DAS ---

    def _resolve_das_direction(self, inputs: InputFrame) -> int:
        """Return the effective shift direction (-1/0/+1) for this frame.

        With both directions held, a fresh press wins; otherwise the current
        direction is kept (deterministic).
        """
        if inputs.left_held and not inputs.right_held:
            return -1
        if inputs.right_held and not inputs.left_held:
            return +1
        if inputs.left_held and inputs.right_held:
            if inputs.left_pressed and not inputs.right_pressed:
                return -1
            if inputs.right_pressed and not inputs.left_pressed:
                return +1
            return self._das_dir
        return 0

    def _update_das(self, inputs: InputFrame) -> None:
        """Horizontal shifting: DAS 10 frames, ARR 2 frames (D5).

        A fresh direction shifts immediately and resets the charge
        (direction change mid-DAS resets the charge, D5); a held direction
        charges 1/frame and auto-shifts every ARR frames once full. The
        charge persists across lock/spawn (D5/D26/D27).
        """
        desired = self._resolve_das_direction(inputs)
        if desired == 0:
            self._das_dir = 0
            self._das_charge = 0
            return
        if desired != self._das_dir:
            self._das_dir = desired
            self._das_charge = 0
            self._try_move(desired, 0)
            return
        self._das_charge = min(self._das_charge + 1, DAS_FRAMES)
        if self._das_charge >= DAS_FRAMES:
            if self._try_move(desired, 0):
                self._das_charge = DAS_FRAMES - ARR_FRAMES

    def _das_accrue_only(self, inputs: InputFrame) -> None:
        """DAS handling during the clear animation (D27): held-state charge
        keeps accruing, capped at full charge; no piece is shifted and press
        events cause no movement."""
        desired = self._resolve_das_direction(inputs)
        if desired == 0:
            self._das_dir = 0
            self._das_charge = 0
        elif desired != self._das_dir:
            self._das_dir = desired
            self._das_charge = 0
        else:
            self._das_charge = min(self._das_charge + 1, DAS_FRAMES)

    # --- Spawn / hold / lock ---

    def _spawn(self, kind: PieceKind, events: list[GameEvent]) -> None:
        """Place ``kind`` at its D27 spawn cells; check block-out BEFORE the
        immediate one-row spawn drop (D27); reset per-piece timers."""
        self._kind = kind
        self._rot = 0
        self._origin = pieces.spawn_origin(kind)
        self._grav_acc = 0
        self._lock_timer = 0
        self._lock_resets = 0
        self._was_grounded = False
        events.append(GameEvent.SPAWN)
        cells = self._cells()
        if self._board.collides(cells):
            # Block-out: spawning piece overlaps a block (D25).
            self._over = True
            events.append(GameEvent.TOP_OUT)
            return
        self._lowest_row = min(row for _, row in cells)
        # Immediate spawn drop (D27): if the cell below is free, fall one row.
        self._try_move(0, -1)

    def _spawn_from_bag(self, events: list[GameEvent]) -> None:
        """Deal the next Bag piece and spawn it; count it once here (D8)."""
        kind = self._bag.next()
        self._piece_counts[kind] += 1
        self._spawn(kind, events)

    def _do_hold(self, events: list[GameEvent]) -> None:
        """Hold (D3/D19): first hold stashes and spawns the next bag piece;
        later holds swap. Disabled until the next lock. A swapped-in piece
        spawns per D25/D27 but is NOT re-counted (D8)."""
        events.append(GameEvent.HOLD_USED)
        self._hold_available = False
        stashed = self._hold_kind
        self._hold_kind = self._kind
        if stashed is None:
            self._spawn_from_bag(events)
        else:
            self._spawn(stashed, events)

    def _lock_piece(self, events: list[GameEvent]) -> None:
        """Lock the active piece: fix cells, re-enable hold, check lock-out,
        score/start any clear (at the pre-clear level, D7), or schedule the
        next spawn for the next frame (no ARE, D26)."""
        assert self._kind is not None
        cells = self._cells()
        kind = self._kind
        self._board.lock(cells, kind)
        events.append(GameEvent.LOCK)
        self._hold_available = True  # re-enabled at next lock (D19)
        self._kind = None
        if all(row > VISIBLE_ROWS for _, row in cells):
            # Lock-out: ALL cells above row 20 (D25).
            self._over = True
            events.append(GameEvent.TOP_OUT)
            return
        rows = self._board.full_rows()
        if rows:
            n = len(rows)
            pre_level = self.level  # score before any level-up (D7 edge)
            self._score_raw += scoring.clear_points(n, pre_level)
            self._lines += n
            events.append(_CLEAR_EVENTS[n])
            if self.level > pre_level:
                events.append(GameEvent.LEVEL_UP)
            self._clearing = list(rows)
            self._clear_frames_left = CLEAR_ANIMATION_FRAMES
        else:
            self._spawn_pending = True
