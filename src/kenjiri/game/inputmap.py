"""Input frame data for Kenjiri — pure data, no pygame.

The UI layer samples the keyboard once per logic frame and hands the game an
:class:`InputFrame`. Per action there are two flags: ``*_pressed`` is the
EDGE (went down this frame) and ``*_held`` is the LEVEL (down this frame).
The seven actions map to the D4 controls: left, right, soft_drop, rotate_cw,
rotate_ccw, hard_drop, hold.
"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import Iterable, Literal

Action = Literal[
    "left", "right", "soft_drop", "rotate_cw", "rotate_ccw", "hard_drop", "hold"
]

ACTIONS: tuple[Action, ...] = typing.get_args(Action)
"""All seven input actions, in canonical order."""


@dataclass(frozen=True)
class InputFrame:
    """One logic frame of player input.

    ``*_pressed`` = edge (key went down this frame); ``*_held`` = level (key
    is down this frame). A pressed flag implies the matching held flag when
    frames are built with :func:`make_frame`.
    """

    left_pressed: bool = False
    left_held: bool = False
    right_pressed: bool = False
    right_held: bool = False
    soft_drop_pressed: bool = False
    soft_drop_held: bool = False
    rotate_cw_pressed: bool = False
    rotate_cw_held: bool = False
    rotate_ccw_pressed: bool = False
    rotate_ccw_held: bool = False
    hard_drop_pressed: bool = False
    hard_drop_held: bool = False
    hold_pressed: bool = False
    hold_held: bool = False


IDLE_FRAME = InputFrame()
"""A frame with no input at all."""


def make_frame(
    held: Iterable[Action] = (), prev_held: Iterable[Action] = ()
) -> InputFrame:
    """Build an :class:`InputFrame` from this frame's held actions and the
    previous frame's held actions.

    Edges are derived: an action is ``pressed`` when it is held now and was
    not held on the previous frame. Raises ``ValueError`` on unknown action
    names.
    """
    now = frozenset(held)
    before = frozenset(prev_held)
    unknown = (now | before) - set(ACTIONS)
    if unknown:
        raise ValueError(f"unknown input action(s): {sorted(unknown)}")
    flags: dict[str, bool] = {}
    for action in ACTIONS:
        flags[f"{action}_held"] = action in now
        flags[f"{action}_pressed"] = action in now and action not in before
    return InputFrame(**flags)
