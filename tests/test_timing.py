"""Tests for :mod:`kenjiri.ui.timing` — the D28 FrameClock.

D28 verbatim: the fixed-timestep accumulator is "clamped to a maximum
catch-up of 3 logic frames (50 ms) per render frame; any measured frame gap
> 250 ms discards the excess time and auto-pauses".

Exact acceptance (frozen plan, T6):
- elapsed 0.016 s -> 1 frame
- elapsed 0.2 s   -> 3 frames (clamped), no auto-pause
- elapsed 0.3 s   -> 0 frames owed + ``auto_pause_triggered`` True

Negatives:
- never more than 3 owed frames per call, regardless of gap
- auto-pause only ever triggers via the > 250 ms path
"""
from __future__ import annotations

import ast
import inspect

from kenjiri.ui import timing
from kenjiri.ui.timing import (
    FRAME_SECONDS,
    MAX_CATCHUP_FRAMES,
    STALL_DISCARD_SECONDS,
    FrameClock,
)


class TestAcceptance:
    """The three exact D28 acceptance points from the frozen plan."""

    def test_typical_frame_owes_one(self) -> None:
        clock = FrameClock()
        assert clock.owed(0.016) == 1
        assert clock.auto_pause_triggered is False

    def test_stall_clamps_to_three_without_auto_pause(self) -> None:
        clock = FrameClock()
        assert clock.owed(0.2) == 3
        assert clock.auto_pause_triggered is False

    def test_large_gap_discards_and_auto_pauses(self) -> None:
        clock = FrameClock()
        assert clock.owed(0.3) == 0
        assert clock.auto_pause_triggered is True


class TestClampNegative:
    """Never more than 3 owed frames per call, regardless of gap."""

    def test_single_calls_never_exceed_three(self) -> None:
        for elapsed in (0.0, 0.001, 0.016, 1 / 60, 0.05, 0.1, 0.2, 0.25, 0.3, 5.0):
            clock = FrameClock()
            owed = clock.owed(elapsed)
            assert 0 <= owed <= MAX_CATCHUP_FRAMES, f"elapsed={elapsed} owed={owed}"

    def test_sustained_stalls_never_exceed_three(self) -> None:
        clock = FrameClock()
        for _ in range(50):
            owed = clock.owed(0.2)
            assert 0 <= owed <= MAX_CATCHUP_FRAMES

    def test_mixed_cadence_never_exceeds_three(self) -> None:
        clock = FrameClock()
        pattern = (0.016, 0.2, 1 / 60, 0.0, 0.1, 0.25, 0.016, 0.3, 0.05)
        for _ in range(30):
            for elapsed in pattern:
                assert 0 <= clock.owed(elapsed) <= MAX_CATCHUP_FRAMES

    def test_leftover_catchup_stays_bounded(self) -> None:
        """After a clamped stall, later catch-up calls are still <= 3."""
        clock = FrameClock()
        assert clock.owed(0.25) == MAX_CATCHUP_FRAMES
        for _ in range(10):
            assert clock.owed(0.016) <= MAX_CATCHUP_FRAMES


class TestAutoPauseNegative:
    """Auto-pause only via the > 250 ms path (D28)."""

    def test_no_auto_pause_at_or_below_threshold(self) -> None:
        for millis in range(0, 251, 5):
            clock = FrameClock()
            clock.owed(millis / 1000.0)
            assert clock.auto_pause_triggered is False, f"paused at {millis} ms"

    def test_exactly_250ms_does_not_auto_pause(self) -> None:
        clock = FrameClock()
        owed = clock.owed(STALL_DISCARD_SECONDS)
        assert clock.auto_pause_triggered is False
        assert owed == MAX_CATCHUP_FRAMES

    def test_above_threshold_always_auto_pauses_and_owes_zero(self) -> None:
        for elapsed in (0.251, 0.26, 0.3, 1.0, 60.0):
            clock = FrameClock()
            assert clock.owed(elapsed) == 0, f"elapsed={elapsed}"
            assert clock.auto_pause_triggered is True

    def test_sustained_small_frames_never_auto_pause(self) -> None:
        clock = FrameClock()
        for _ in range(1000):
            clock.owed(0.016)
            assert clock.auto_pause_triggered is False

    def test_flag_resets_on_next_call(self) -> None:
        clock = FrameClock()
        clock.owed(0.3)
        assert clock.auto_pause_triggered is True
        assert clock.owed(0.016) == 1
        assert clock.auto_pause_triggered is False

    def test_discard_drops_excess_time(self) -> None:
        """A > 250 ms gap discards ALL banked time — the next normal frame
        owes exactly one frame, not a catch-up burst."""
        clock = FrameClock()
        clock.owed(0.2)  # banks leftover catch-up
        clock.owed(0.3)  # discards it
        assert clock.owed(1 / 60) == 1


class TestAccumulator:
    """Fixed-timestep bookkeeping: no long-run drift, no invented frames."""

    def test_600_ideal_frames_owe_exactly_600(self) -> None:
        clock = FrameClock()
        total = sum(clock.owed(FRAME_SECONDS) for _ in range(600))
        assert total == 600

    def test_uneven_cadence_tracks_wall_clock(self) -> None:
        clock = FrameClock()
        total = sum(clock.owed(0.033) for _ in range(300))
        # 9.9 s of wall clock ~= 594 logic frames.
        assert abs(total - round(0.033 * 300 / FRAME_SECONDS)) <= 1

    def test_zero_elapsed_owes_nothing_on_fresh_clock(self) -> None:
        clock = FrameClock()
        assert clock.owed(0.0) == 0

    def test_negative_elapsed_is_ignored(self) -> None:
        clock = FrameClock()
        assert clock.owed(-1.0) == 0
        assert clock.auto_pause_triggered is False


def test_timing_module_is_pure_no_pygame() -> None:
    """FrameClock is pure per the interface contract: no pygame import."""
    tree = ast.parse(inspect.getsource(timing))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "pygame" for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "pygame"
