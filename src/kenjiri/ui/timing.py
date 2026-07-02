"""Fixed-timestep frame accounting for Kenjiri (D28) — PURE, no pygame.

D28 verbatim: the fixed-timestep accumulator is "clamped to a maximum
catch-up of 3 logic frames (50 ms) per render frame; any measured frame gap
> 250 ms discards the excess time and auto-pauses".

:class:`FrameClock` converts measured wall-clock gaps between render frames
into the number of 60 fps logic frames owed. The fractional remainder is
carried exactly (nearest-frame rounding with carry), so long runs track the
wall clock with zero drift, while the two D28 guards make window drags,
resizes and minimizes unable to fast-forward the game unseen:

- catch-up is clamped to 3 logic frames per :meth:`FrameClock.owed` call,
  and the banked backlog itself is capped at the same 50 ms budget;
- a measured gap above 250 ms discards ALL banked time, owes 0 frames and
  raises :attr:`FrameClock.auto_pause_triggered` for exactly one call (the
  app auto-pauses the gameplay scene, D28 — gameplay scene only).
"""
from __future__ import annotations

FPS = 60
"""Logic frames per second — the 60 fps reference (D5/D6/D23)."""

FRAME_SECONDS = 1.0 / FPS
"""Duration of one logic frame."""

MAX_CATCHUP_FRAMES = 3
"""D28: maximum catch-up of 3 logic frames (50 ms) per render frame."""

MAX_BACKLOG_SECONDS = MAX_CATCHUP_FRAMES * FRAME_SECONDS
"""The 50 ms catch-up budget (D28) — banked time never exceeds it."""

STALL_DISCARD_SECONDS = 0.25
"""D28: any measured frame gap > 250 ms discards the excess time and
auto-pauses."""


class FrameClock:
    """Owed-logic-frame accountant implementing the D28 stall policy.

    Call :meth:`owed` once per render frame with the measured elapsed
    seconds since the previous call; run the game's logic step exactly that
    many times. Check :attr:`auto_pause_triggered` after every call.
    """

    def __init__(self) -> None:
        """Start with an empty accumulator and no pending auto-pause."""
        self._accumulator = 0.0
        self._auto_pause_triggered = False

    @property
    def auto_pause_triggered(self) -> bool:
        """True when the LAST :meth:`owed` call measured a gap > 250 ms
        (D28). Resets on the next call."""
        return self._auto_pause_triggered

    def owed(self, elapsed_s: float) -> int:
        """Return the logic frames owed for a render-frame gap of
        ``elapsed_s`` seconds.

        Implements D28 verbatim: at most :data:`MAX_CATCHUP_FRAMES` frames
        are returned per call; a gap greater than
        :data:`STALL_DISCARD_SECONDS` discards all banked time, returns 0
        and sets :attr:`auto_pause_triggered`. Negative gaps (clock
        weirdness) are ignored.

        Args:
            elapsed_s: Measured wall-clock seconds since the previous call.

        Returns:
            The number of logic frames to step now (0..3).
        """
        self._auto_pause_triggered = False
        if elapsed_s > STALL_DISCARD_SECONDS:
            # D28: discard the excess time and auto-pause.
            self._accumulator = 0.0
            self._auto_pause_triggered = True
            return 0
        if elapsed_s > 0.0:
            self._accumulator += elapsed_s
        # Nearest-frame rounding with exact remainder carry: no long-run
        # drift, and a typical ~16 ms render frame owes exactly 1 frame.
        frames = round(self._accumulator * FPS)
        if frames <= 0:
            return 0
        if frames > MAX_CATCHUP_FRAMES:
            frames = MAX_CATCHUP_FRAMES
        self._accumulator -= frames * FRAME_SECONDS
        if self._accumulator > MAX_BACKLOG_SECONDS:
            # Cap the banked backlog at the 50 ms catch-up budget (D28):
            # sustained stalls must never bank a fast-forward burst.
            self._accumulator = MAX_BACKLOG_SECONDS
        return frames
