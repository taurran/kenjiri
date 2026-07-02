"""Kenjiri app shell: window, fixed-timestep loop, scene driver (D16/D28).

- 256x240 internal canvas (NES resolution), resizable window defaulting to
  3x = 768x720; rendering letterboxes at the LARGEST integer scale that
  fits, via ``pygame.transform.scale`` (nearest-neighbor) ONLY — never
  smoothscale (D16). Window title "Kenjiri" (D23).
- Fixed-timestep 60 Hz logic driven by :class:`kenjiri.ui.timing.FrameClock`
  (D28: max 3 logic frames catch-up per render frame; gaps > 250 ms discard
  and auto-pause). Auto-pause also fires on window focus loss and minimize
  — gameplay scene only (D28).
- Mixer failure means the game runs silent (D24) — :class:`Audio` wraps its
  own init and no-ops when degraded.
- :func:`run_smoke` is the headless self-check behind ``--smoke``: dummy
  SDL drivers as the fallback, every scene constructed and rendered
  offscreen (title, gameplay, pause, a real driven-to-top-out game over),
  exit 0.
"""
from __future__ import annotations

import os
import time

import pygame

from kenjiri.audio.engine import Audio
from kenjiri.gfx.palette import PALETTE
from kenjiri.persistence import applog, paths
from kenjiri.persistence.highscore import HighScoreStore
from kenjiri.ui.hud import CANVAS_SIZE
from kenjiri.ui.scenes import GameplayScene, TitleScene
from kenjiri.ui.timing import FrameClock

__all__ = ["App", "run_smoke"]

WINDOW_TITLE = "Kenjiri"
"""Window title (D23)."""

DEFAULT_SCALE = 3
"""Default window scale: 3x = 768x720 (D16)."""

_LETTERBOX_COLOR_KEY = "OUTLINE"
_RENDER_FPS_LIMIT = 60


class App:
    """The Kenjiri application: owns the display, audio, store and scenes."""

    def __init__(self, smoke: bool = False) -> None:
        """Initialise pygame, the window, audio and persistence.

        Args:
            smoke: When True, use a session-only high-score store (no real
                ``%LOCALAPPDATA%`` writes) and a 1x window — the headless
                self-check never needs a visible window.
        """
        applog.get_logger()
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        size = (
            CANVAS_SIZE
            if smoke
            else (CANVAS_SIZE[0] * DEFAULT_SCALE, CANVAS_SIZE[1] * DEFAULT_SCALE)
        )
        self._window = pygame.display.set_mode(size, pygame.RESIZABLE)
        self._canvas = pygame.Surface(CANVAS_SIZE)
        self._audio = Audio()  # wraps mixer init; silent on failure (D24)
        self._store = HighScoreStore(None if smoke else paths.db_path())
        self._frame_clock = FrameClock()
        self._running = False
        self._scene: TitleScene | GameplayScene = TitleScene(self)
        self._scene.enter()

    # ------------------------------------------------------------- services

    @property
    def audio(self) -> Audio:
        """The shared audio engine."""
        return self._audio

    @property
    def store(self) -> HighScoreStore:
        """The shared high-score store."""
        return self._store

    def switch(self, scene: TitleScene | GameplayScene) -> None:
        """Make *scene* current and call its ``enter()`` hook."""
        self._scene = scene
        scene.enter()

    def quit(self) -> None:
        """Stop the main loop after the current iteration."""
        self._running = False

    # ------------------------------------------------------------ main loop

    def run(self) -> int:
        """Run the fixed-timestep main loop until quit; return exit code."""
        self._running = True
        render_clock = pygame.time.Clock()
        last = time.perf_counter()
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type in (
                    pygame.WINDOWFOCUSLOST,
                    pygame.WINDOWMINIMIZED,
                ):
                    self._scene.auto_pause()  # D28 (gameplay scene only)
                else:
                    self._scene.handle_event(event)
            now = time.perf_counter()
            owed = self._frame_clock.owed(now - last)
            last = now
            if self._frame_clock.auto_pause_triggered:
                self._scene.auto_pause()  # D28 stall path
            for _ in range(owed):
                self._scene.update()
            self._render()
            render_clock.tick(_RENDER_FPS_LIMIT)
        self._store.close()
        pygame.quit()
        return 0

    def _render(self) -> None:
        """Draw the scene to the canvas and letterbox it into the window.

        Largest integer scale that fits, nearest-neighbor only (D16);
        windows smaller than 1x clamp to 1x (D24).
        """
        self._scene.draw(self._canvas)
        window = self._window
        win_w, win_h = window.get_size()
        scale = max(
            1, min(win_w // CANVAS_SIZE[0], win_h // CANVAS_SIZE[1])
        )
        scaled_size = (CANVAS_SIZE[0] * scale, CANVAS_SIZE[1] * scale)
        # D16: nearest-neighbor ONLY — pygame.transform.scale, never
        # smoothscale.
        scaled = pygame.transform.scale(self._canvas, scaled_size)
        window.fill(PALETTE[_LETTERBOX_COLOR_KEY])
        window.blit(
            scaled,
            ((win_w - scaled_size[0]) // 2, (win_h - scaled_size[1]) // 2),
        )
        pygame.display.flip()

    # ---------------------------------------------------------------- smoke

    def smoke(self) -> int:
        """Headless self-check: render one frame of every scene/state.

        Constructs the title scene, a live gameplay scene, its paused state
        and a REAL game-over state (a fresh run driven to top-out with hard
        drops), rendering each through the full letterbox pipeline. Raises
        on any failure; returns 0 on success.
        """
        title = TitleScene(self)
        self.switch(title)
        title.update()
        self._render()

        gameplay = GameplayScene(self)
        self.switch(gameplay)
        for _ in range(5):
            gameplay.update()
        self._render()

        gameplay.auto_pause()
        if not gameplay.paused:
            raise RuntimeError("smoke: gameplay scene did not auto-pause")
        gameplay.update()
        self._render()
        # Resume via the real key path (D4: P resumes).
        gameplay.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)
        )
        if gameplay.paused:
            raise RuntimeError("smoke: gameplay scene did not resume")

        space_down = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        space_up = pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE)
        for step in range(4000):
            if gameplay.game_over:
                break
            gameplay.handle_event(space_down if step % 2 == 0 else space_up)
            gameplay.update()
        if not gameplay.game_over:
            raise RuntimeError("smoke: hard-drop run never topped out")
        gameplay.update()
        self._render()

        self._store.close()
        pygame.quit()
        return 0


def run_smoke() -> int:
    """Entry for ``python -m kenjiri --smoke`` (headless CI-safe, exit 0).

    Uses SDL dummy video/audio drivers as the fallback (only when the
    environment has not already chosen drivers), so no window or audio
    device is required.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    return App(smoke=True).smoke()
