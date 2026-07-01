"""Tests for kenjiri.game.state — the full rules state machine — and
kenjiri.game.inputmap.

Board setups use ``Game.board.lock`` (public API) to construct positions;
a few tests poke documented private fields (``_lines``, ``_score_raw``,
``_lock_resets``, ``_das_charge``) where reaching the state through play
alone would need hundreds of scripted frames.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from kenjiri.game import pieces
from kenjiri.game.bag import SevenBag
from kenjiri.game.inputmap import ACTIONS, IDLE_FRAME, Action, InputFrame, make_frame
from kenjiri.game.state import (
    ARR_FRAMES,
    CLEAR_ANIMATION_FRAMES,
    DAS_FRAMES,
    LOCK_DELAY_FRAMES,
    MAX_LOCK_RESETS,
    Game,
    GameEvent,
)

E = GameEvent


def seed_for_first(kind: str) -> int:
    """Find a seed whose 7-bag deals ``kind`` first (deterministic)."""
    for seed in range(5000):
        if SevenBag(random.Random(seed)).peek(1)[0] == kind:
            return seed
    raise AssertionError(f"no seed found dealing {kind} first")


def row_cells(row: int, cols: Iterable[int]) -> list[tuple[int, int]]:
    """Cells across ``cols`` of ``row``."""
    return [(col, row) for col in cols]


def col_cells(col: int, rows: Iterable[int]) -> list[tuple[int, int]]:
    """Cells down ``rows`` of ``col``."""
    return [(col, row) for row in rows]


class Driver:
    """Steps a Game with held-set scripting; derives press edges."""

    def __init__(self, seed: int = 0) -> None:
        self.game = Game(random.Random(seed))
        self._prev: frozenset[Action] = frozenset()
        self.log: list[list[GameEvent]] = []

    def step(self, held: Iterable[Action] = ()) -> list[GameEvent]:
        """Advance one frame with ``held`` actions down."""
        frame = make_frame(held, self._prev)
        self._prev = frozenset(held)
        events = self.game.step(frame)
        self.log.append(events)
        return events

    def steps(self, n: int, held: Iterable[Action] = ()) -> list[GameEvent]:
        """Advance ``n`` frames; return all events concatenated."""
        out: list[GameEvent] = []
        for _ in range(n):
            out.extend(self.step(held))
        return out

    def min_row(self) -> int:
        active = self.game.active
        assert active is not None
        return min(row for _, row in active.cells)

    def min_col(self) -> int:
        active = self.game.active
        assert active is not None
        return min(col for col, _ in active.cells)


# ---------------------------------------------------------------------------
# inputmap
# ---------------------------------------------------------------------------


class TestInputFrame:
    def test_idle_frame_all_false(self) -> None:
        for action in ACTIONS:
            assert getattr(IDLE_FRAME, f"{action}_pressed") is False
            assert getattr(IDLE_FRAME, f"{action}_held") is False

    def test_pressed_is_edge_only(self) -> None:
        first = make_frame({"left"})
        assert first.left_pressed and first.left_held
        second = make_frame({"left"}, {"left"})
        assert not second.left_pressed
        assert second.left_held

    def test_release_clears_both(self) -> None:
        frame = make_frame((), {"hard_drop"})
        assert not frame.hard_drop_pressed and not frame.hard_drop_held

    def test_unknown_action_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_frame({"jump"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Spawn (D25/D27)
# ---------------------------------------------------------------------------


class TestSpawn:
    def test_spawn_emits_spawn_and_immediately_drops_one_row(self) -> None:
        d = Driver(seed_for_first("T"))
        events = d.step()
        assert events == [E.SPAWN]
        # T spawn cells rows 21-22 fell one row on the spawn frame (D27).
        assert d.game.active is not None
        assert d.game.active.cells == frozenset(
            {(4, 20), (5, 20), (6, 20), (5, 21)}
        )
        assert d.game.piece_counts["T"] == 1

    def test_spawn_drop_suppressed_when_cell_below_occupied(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game.board.lock(row_cells(20, [4, 5, 6]), "O")
        d.step()
        assert not d.game.over
        assert d.game.active is not None
        assert min(row for _, row in d.game.active.cells) == 21
        # Ghost suppressed while the piece is entirely in the Buffer (D25).
        assert d.game.active.ghost_cells is None

    def test_block_out_at_spawn_position_before_drop(self) -> None:
        d = Driver(seed_for_first("T"))
        # Occupy one exact spawn cell: overlap = block-out (D25/D27).
        d.game.board.lock([(5, 21)], "O")
        events = d.step()
        assert events == [E.SPAWN, E.TOP_OUT]
        assert d.game.over

    def test_ghost_is_piece_dropped_to_rest(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step()
        assert d.game.active is not None
        assert d.game.active.ghost_cells == frozenset(
            {(4, 1), (5, 1), (6, 1), (5, 2)}
        )


# ---------------------------------------------------------------------------
# Top-out (D25)
# ---------------------------------------------------------------------------


class TestTopOut:
    def test_lock_out_when_all_cells_above_row_20(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game.board.lock(row_cells(20, [4, 5, 6]), "O")  # blocks the drop
        events = d.step({"hard_drop"})  # grounded at rows 21-22, 0-row drop
        assert events == [E.SPAWN, E.HARD_DROP, E.LOCK, E.TOP_OUT]
        assert d.game.over

    def test_partial_lock_above_row_20_is_legal(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game.board.lock(row_cells(19, [4, 5, 6]), "O")
        events = d.step({"hard_drop"})  # locks rows 20-21: legal (D25)
        assert E.TOP_OUT not in events
        assert E.LOCK in events
        assert not d.game.over
        # The Buffer-row cell persists invisibly (D25).
        assert d.game.board.cell(5, 21) == "T"

    def test_no_events_after_game_over(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game.board.lock([(5, 21)], "O")
        d.step()
        assert d.game.over
        assert d.step({"hard_drop"}) == []
        assert d.step() == []


# ---------------------------------------------------------------------------
# Gravity in play (D6) + soft drop (D5/D7)
# ---------------------------------------------------------------------------


class TestGravityInPlay:
    def test_level_0_falls_one_row_every_48_frames(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step()
        assert d.min_row() == 20
        d.steps(46)  # accumulator at 47/48
        assert d.min_row() == 20
        d.step()  # 48th frame after spawn: falls
        assert d.min_row() == 19

    def test_soft_drop_is_20x_gravity_and_scores_1_per_row(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step({"soft_drop"})  # spawn frame: 20/48 accumulated
        d.steps(11, {"soft_drop"})  # 12 frames x 20 units = 5 rows exactly
        assert d.min_row() == 20 - 5
        assert d.game.score == 5

    def test_soft_drop_capped_at_1_row_per_frame_at_floor_gravity(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game._lines = 150  # level 15: 4-frame floor (documented poke)
        d.step({"soft_drop"})  # spawn frame: immediate drop + 1 capped fall
        assert d.min_row() == 19
        d.step({"soft_drop"})
        assert d.min_row() == 18  # exactly 1 row/frame, never 2

    def test_soft_drop_onto_ground_does_not_skip_lock_delay(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game._lines = 150  # floor gravity to reach ground fast
        d.step({"soft_drop"})
        while d.min_row() > 1:
            assert E.LOCK not in d.step({"soft_drop"})
        landing_frame = len(d.log) - 1
        # Grounded now; releasing soft drop, the 0.5 s delay still applies.
        lock_frame = None
        for _ in range(LOCK_DELAY_FRAMES + 5):
            if E.LOCK in d.step():
                lock_frame = len(d.log) - 1
                break
        assert lock_frame is not None
        assert lock_frame - landing_frame >= LOCK_DELAY_FRAMES - 1


# ---------------------------------------------------------------------------
# Lock delay (D18)
# ---------------------------------------------------------------------------


class TestLockDelay:
    def _grounded_driver(self) -> Driver:
        """T grounded from its spawn frame on a row-19 shelf (cols 1-9)."""
        d = Driver(seed_for_first("T"))
        d.game.board.lock(row_cells(19, range(1, 10)), "O")
        d.step()  # spawn frame: grounded, timer = 1
        return d

    def test_locks_after_30_grounded_frames(self) -> None:
        d = self._grounded_driver()
        events = d.steps(LOCK_DELAY_FRAMES - 2)
        assert E.LOCK not in events
        assert E.LOCK in d.step()  # frame index 29: 30 grounded frames

    def test_grounded_moves_reset_at_most_15_times_then_lock(self) -> None:
        d = self._grounded_driver()
        # 20 alternating grounded shifts, one per frame (each a press edge).
        for i in range(20):
            events = d.step({"left"} if i % 2 == 0 else {"right"})
            assert E.LOCK not in events
        # Resets 1-15 (frames 1-15) restarted the timer; moves 16-20 did
        # not: the timer has run since frame 15 and expires at frame 44.
        assert d.game._lock_resets == MAX_LOCK_RESETS
        events = d.steps(23)  # frames 21-43
        assert E.LOCK not in events
        assert E.LOCK in d.step()  # frame 44

    def test_hard_drop_locks_instantly_and_scores_2_per_row(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step()
        events = d.step({"hard_drop"})  # falls rows 20 -> 1: 19 rows
        assert events == [E.HARD_DROP, E.LOCK]
        assert d.game.score == 19 * 2
        # No ARE: next piece spawns on the very next logic frame (D26).
        assert E.SPAWN in d.step()

    def test_reset_counter_clears_on_fall_to_new_lowest_row(self) -> None:
        d = Driver(seed_for_first("T"))
        d.game.board.lock(row_cells(19, [4, 5, 6]), "O")  # narrow ledge
        d.step()  # grounded on the ledge, rows 20-21
        d.step({"left"})  # reset 1
        d.step({"right"})  # reset 2
        assert d.game._lock_resets == 2
        d.step()  # release, so each walk press below is a fresh edge
        # Walk right off the ledge: cols 7-9 have no support.
        for _ in range(3):
            d.step({"right"})
            d.step()
        # Fall to the floor with soft drop; new lowest row clears resets.
        while d.min_row() >= 20:
            d.step({"soft_drop"})
        assert d.game._lock_resets == 0
        # And the piece still locks normally at the floor afterwards.
        locked = False
        for _ in range(200):
            if E.LOCK in d.step({"soft_drop"}):
                locked = True
                break
        assert locked
        assert not d.game.over

    def test_force_lock_on_ground_contact_when_resets_exhausted(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step()
        d.step({"soft_drop"})  # airborne, descending
        d.game._lock_resets = MAX_LOCK_RESETS  # documented poke: exhausted
        d.game._lowest_row = 1  # a lower row must not clear the counter
        prev_min_row = d.min_row()
        lock_frame_prev_min: int | None = None
        for _ in range(200):
            events = d.step({"soft_drop"})
            if E.LOCK in events:
                lock_frame_prev_min = prev_min_row
                break
            if d.game.active is not None:
                prev_min_row = d.min_row()
        # Force-lock fired on the very frame of ground contact: one frame
        # earlier the piece was still one row above the floor. (With the
        # normal 0.5 s delay it would have SAT at row 1 for ~30 frames.)
        assert lock_frame_prev_min == 2


# ---------------------------------------------------------------------------
# DAS / ARR (D5/D26/D27)
# ---------------------------------------------------------------------------


class TestDas:
    def test_das_10_frames_then_arr_2_frames(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step({"right"})  # spawn frame: press shifts immediately
        assert d.min_col() == 5
        d.steps(9, {"right"})  # charge 1..9: no auto-shift yet
        assert d.min_col() == 5
        d.step({"right"})  # frame 10: DAS full
        assert d.min_col() == 6
        d.step({"right"})
        assert d.min_col() == 6
        d.step({"right"})  # frame 12: ARR
        assert d.min_col() == 7
        d.steps(2, {"right"})  # frame 14: ARR
        assert d.min_col() == 8  # cols 8-10: at the wall
        d.steps(4, {"right"})
        assert d.min_col() == 8  # never shifts into the wall

    def test_direction_change_mid_das_resets_charge(self) -> None:
        d = Driver(seed_for_first("T"))
        d.step({"right"})  # immediate shift to cols 5-7
        d.steps(5, {"right"})  # mid-charge
        d.step({"left"})  # switch: immediate shift back, charge reset
        assert d.min_col() == 4
        events_cols = [d.min_col() for _ in range(9) if d.step({"left"}) or True]
        assert events_cols == [4] * 9  # charge 1..9 after the switch
        d.step({"left"})  # 10 frames after the switch: auto-shift
        assert d.min_col() == 3

    def test_das_charge_held_through_hard_drop_into_next_spawn(self) -> None:
        d = Driver(seed_for_first("T"))
        d.steps(12, {"right"})  # charged and auto-shifting
        d.step({"right", "hard_drop"})  # lock; right stays held
        assert d.game._das_charge == DAS_FRAMES - ARR_FRAMES  # not reset
        d.step({"right"})  # next piece spawns this frame
        assert d.game.active is not None
        spawn_cells = d.game.active.cells
        d.step({"right"})  # charge tops up: shift 1 frame later, not 10
        assert d.game.active is not None
        assert d.game.active.cells == frozenset(
            (col + 1, row) for col, row in spawn_cells
        )


# ---------------------------------------------------------------------------
# Line clears, animation, DAS accrual during it (D23/D26/D27)
# ---------------------------------------------------------------------------


def pilot_vertical_i_to_column_10(d: Driver) -> None:
    """With an I freshly active: rotate CW and shift to column 10."""
    assert d.game.active is not None and d.game.active.kind == "I"
    d.step({"rotate_cw"})  # vertical at column 6
    for _ in range(4):
        d.step({"right"})
        d.step()


class TestLineClear:
    def test_single_clear_animation_18_frames_then_spawn_next_frame(self) -> None:
        d = Driver(seed_for_first("I"))
        d.game.board.lock(row_cells(1, range(1, 10)), "O")
        d.step()
        pilot_vertical_i_to_column_10(d)
        events = d.step({"hard_drop"})  # locks (10,1)-(10,4): row 1 full
        assert events == [E.HARD_DROP, E.LOCK, E.CLEAR_SINGLE]
        assert d.game.clearing == [1]
        assert d.game.active is None
        assert d.game.score == 17 * 2 + 40  # drop 17 rows + Single at L0
        assert d.game.lines == 1
        # Exactly 18 animation frames, all event-silent.
        for i in range(CLEAR_ANIMATION_FRAMES):
            assert d.game.clearing == [1]
            assert d.step() == []
        assert d.game.clearing is None
        # No additional ARE: next piece spawns on the next logic frame.
        assert E.SPAWN in d.step()
        # Collapse happened: the I stack dropped one row.
        assert d.game.board.cell(10, 1) == "I"
        assert d.game.board.cell(10, 4) is None

    def test_input_events_ignored_during_clear_but_das_accrues(self) -> None:
        d = Driver(seed_for_first("I"))
        d.game.board.lock(row_cells(1, range(1, 10)), "O")
        d.step()
        pilot_vertical_i_to_column_10(d)
        d.step({"hard_drop"})
        hold_before = d.game.hold_kind
        # Hold left through the animation; also mash ignored events.
        for i in range(CLEAR_ANIMATION_FRAMES):
            held: set[Action] = {"left"}
            if i == 5:
                held |= {"hold", "hard_drop", "rotate_cw"}
            assert d.step(held) == []
        assert d.game.hold_kind == hold_before  # hold press was ignored
        assert d.game._das_charge == DAS_FRAMES  # capped at full (D27)
        next_kind = d.game.next_kind
        events = d.step({"left"})  # spawn frame: full charge auto-shifts
        assert E.SPAWN in events
        assert d.game.active is not None
        assert d.game.active.cells == frozenset(
            (col - 1, row - 1) for col, row in pieces.spawn_cells(next_kind)
        )

    def test_buffer_row_clear_scores_normally_and_does_not_crash(self) -> None:
        # D25: a line clear in a Buffer row is possible and scores normally.
        d = Driver(seed_for_first("I"))
        d.step()  # I falls to row 20
        d.step({"rotate_cw"})  # vertical at column 6, rows 18-21
        d.game.board.lock([(6, 17)], "O")  # support under the piece
        d.game.board.lock(row_cells(21, [1, 2, 3, 4, 5, 7, 8, 9, 10]), "O")
        events = d.step({"hard_drop"})  # 0-row drop, locks (6,18)-(6,21)
        assert E.CLEAR_SINGLE in events
        assert E.TOP_OUT not in events
        assert d.game.clearing == [21]
        assert d.game.score == 40
        assert d.game.lines == 1
        d.steps(CLEAR_ANIMATION_FRAMES)
        assert d.game.clearing is None
        assert d.game.board.cell(6, 21) is None
        assert d.game.board.cell(6, 20) == "I"
        assert not d.game.over

    def test_double_scores_at_pre_clear_level_and_emits_level_up(self) -> None:
        # D7 edge: a double lifting lines 9 -> 11 scores at level 0, not 1.
        d = Driver(seed_for_first("I"))
        d.game._lines = 9  # documented poke: one line short of level 1
        d.game.board.lock(row_cells(1, range(1, 10)), "O")
        d.game.board.lock(row_cells(2, range(1, 10)), "O")
        d.step()
        pilot_vertical_i_to_column_10(d)
        events = d.step({"hard_drop"})
        assert events == [E.HARD_DROP, E.LOCK, E.CLEAR_DOUBLE, E.LEVEL_UP]
        assert d.game.lines == 11
        assert d.game.level == 1
        # 17-row hard drop (+34) plus Double at PRE-clear level 0: 100 x 1.
        assert d.game.score == 34 + 100


# ---------------------------------------------------------------------------
# Hold (D3/D19) and piece counts (D8)
# ---------------------------------------------------------------------------


class TestHold:
    def test_first_hold_stashes_and_spawns_next(self) -> None:
        d = Driver(0)
        first = d.game.next_kind
        d.step()
        second = d.game.next_kind
        events = d.step({"hold"})
        assert events == [E.HOLD_USED, E.SPAWN]
        assert d.game.hold_kind == first
        assert d.game.active is not None and d.game.active.kind == second
        assert d.game.hold_available is False

    def test_second_hold_within_one_piece_is_rejected(self) -> None:
        d = Driver(0)
        d.step()
        d.step({"hold"})
        held_kind = d.game.hold_kind
        active_kind = d.game.active.kind if d.game.active else None
        d.step()  # release
        events = d.step({"hold"})  # fresh press edge, still same piece
        assert events == []
        assert d.game.hold_kind == held_kind
        assert d.game.active is not None and d.game.active.kind == active_kind

    def test_hold_reenabled_at_next_lock_and_swaps(self) -> None:
        d = Driver(0)
        first = d.game.next_kind
        d.step()
        d.step({"hold"})  # stash first, spawn second
        d.step({"hard_drop"})  # lock second: hold re-enabled (D19)
        assert d.game.hold_available is True
        d.step()  # spawn third
        third = d.game.active.kind if d.game.active else None
        events = d.step({"hold"})  # swap: first comes back
        assert events == [E.HOLD_USED, E.SPAWN]
        assert d.game.active is not None and d.game.active.kind == first
        assert d.game.hold_kind == third

    def test_piece_counts_count_each_piece_once_at_its_spawn(self) -> None:
        d = Driver(0)
        first = d.game.next_kind
        d.step()
        d.step({"hold"})
        d.step({"hard_drop"})
        d.step()
        d.step({"hold"})  # first swaps back in: NOT re-counted (D8)
        counts = d.game.piece_counts
        assert counts[first] == 1
        assert sum(counts.values()) == 3  # exactly the three bag draws


# ---------------------------------------------------------------------------
# Full seeded simulation (acceptance) and negatives
# ---------------------------------------------------------------------------


class TestFullSimulation:
    def test_scripted_seeded_game_reaches_a_kenjiri(self) -> None:
        d = Driver(0)
        d.game.board.lock(row_cells(1, range(1, 10)), "O")
        d.game.board.lock(row_cells(2, range(1, 10)), "O")
        d.game.board.lock(row_cells(3, range(1, 10)), "O")
        d.game.board.lock(row_cells(4, range(1, 10)), "O")
        d.step()  # first spawn
        # Park non-I pieces on top of the stack; the 7-bag guarantees an I
        # within the first seven pieces.
        guard = 0
        while d.game.active is not None and d.game.active.kind != "I":
            d.step({"hard_drop"})
            d.step()
            guard += 1
            assert guard < 8, "7-bag must deal an I within 7 pieces"
        pilot_vertical_i_to_column_10(d)
        events = d.step({"hard_drop"})
        assert E.CLEAR_KENJIRI in events
        assert E.TOP_OUT not in events
        assert d.game.lines == 4
        assert d.game.level == 0
        assert d.game.score >= 1200  # 1200 x (0+1) plus drop points
        d.steps(CLEAR_ANIMATION_FRAMES)
        assert d.game.clearing is None
        assert E.SPAWN in d.step()
        assert not d.game.over

    def test_score_property_caps_at_9_999_999(self) -> None:
        d = Driver(0)
        d.game._score_raw = 123_456_789  # documented poke
        assert d.game.score == 9_999_999

    def test_random_inputs_never_move_piece_into_colliding_cell(self) -> None:
        rng = random.Random(1337)
        d = Driver(42)
        for _ in range(2500):
            n_held = rng.randint(0, 3)
            held = set(rng.sample(ACTIONS, n_held))
            d.step(held)
            if d.game.over:
                break
            active = d.game.active
            if active is None:
                continue
            for col, row in active.cells:
                assert 1 <= col <= 10 and 1 <= row <= 22
                assert d.game.board.cell(col, row) is None
            if active.ghost_cells is not None:
                for col, row in active.ghost_cells:
                    assert 1 <= col <= 10 and 1 <= row <= 22
                    assert d.game.board.cell(col, row) is None

    def test_no_pygame_import_anywhere_in_game_package(self) -> None:
        import kenjiri.game.bag  # noqa: F401
        import kenjiri.game.board  # noqa: F401
        import kenjiri.game.gravity  # noqa: F401
        import kenjiri.game.inputmap  # noqa: F401
        import kenjiri.game.pieces  # noqa: F401
        import kenjiri.game.scoring  # noqa: F401
        import kenjiri.game.state  # noqa: F401

        assert "pygame" not in sys.modules
