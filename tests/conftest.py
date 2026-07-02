"""Shared pytest configuration for Kenjiri.

Forces SDL's dummy video/audio drivers BEFORE pygame is ever imported so the
whole suite runs headless (CI-safe, no window, no audio device), and provides
a session-scoped pygame lifecycle fixture.

gfx modules deliberately avoid ``convert_alpha()`` so no display surface is
ever required; ``pygame.display.set_mode`` is never called by tests either.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Must happen before ANY pygame import anywhere in the test session.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

# src/ layout: make the package importable without requiring an installed dist.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pygame  # noqa: E402  (import order is the point of this file)
import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def pygame_session() -> object:
    """Initialise pygame once for the whole test session (headless)."""
    pygame.init()
    yield
    pygame.quit()
