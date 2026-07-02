"""Kenjiri audio engine — event-driven SFX + music (D11/D12/D24/D26).

Event -> SFX map per D12, including the D26 rule that the rising dog
whistle REPLACES the ordinary clear pop on a 4-line clear (the map simply
routes ``CLEAR_KENJIRI`` to ``kenjiri.wav``), and the D12 sequencing hook
(:meth:`Audio.play_later`) the gameplay scene uses to fire the level-up
bark 300 ms (18 frames) after a same-frame Kenjiri whistle.

Ducking per D26 verbatim: on any SFX the "music drops to 60% volume and
recovers linearly over 250 ms". Pause lowers music volume by 50% (D23).

Degraded mode per D24: mixer/device init failure (or missing asset files)
means the game runs silent — logged once via the ``kenjiri`` logger
(persistence.applog's sink) — and every method of :class:`Audio` no-ops
cleanly. SFX never stack-clip: each distinct sample owns a dedicated mixer
channel, so re-triggering restarts it instead of layering (D12).

Asset resolution works for BOTH dev runs and the PyInstaller onefile exe:
``base = Path(getattr(sys, "_MEIPASS", project_root))`` (D28: the committed
``assets/`` files are canonical; music is WAV per the orchestrator's
board-logged format decision).
"""
from __future__ import annotations

import logging
import sys
from enum import Enum, auto
from pathlib import Path

import pygame

from kenjiri.game.state import GameEvent

_logger = logging.getLogger("kenjiri")

__all__ = ["Audio", "UiSound", "assets_dir"]

FPS = 60
"""Logic frames per second (60 fps reference)."""

DUCK_FRAMES = 15
"""Duck recovery length: 250 ms at 60 fps (D26)."""

DUCK_FLOOR = 0.6
"""Music drops to 60% volume under any SFX (D26)."""

PAUSE_MUSIC_FACTOR = 0.5
"""Pause lowers music volume by 50% (D23)."""

LEVEL_UP_DELAY_FRAMES = 18
"""Whistle -> bark fanfare sequencing gap: 300 ms at 60 fps (D12)."""


class UiSound(Enum):
    """Non-game-event UI sounds (menu blip, D12)."""

    MENU = auto()


#: Music tracks: name -> (filename, loops) — title/gameplay loop seamlessly
#: (D11), the game-over theme plays once (D23).
MUSIC_TRACKS: dict[str, tuple[str, int]] = {
    "title": ("title.wav", -1),
    "gameplay": ("gameplay.wav", -1),
    "gameover": ("gameover.wav", 0),
}

#: Event -> SFX filename per D12/D26. Events absent here (SPAWN) are silent.
_SFX_FILES: dict[Enum, str] = {
    GameEvent.LOCK: "lock.wav",           # soft thud
    GameEvent.HARD_DROP: "harddrop.wav",  # heavier slam
    GameEvent.CLEAR_SINGLE: "clear.wav",  # pop
    GameEvent.CLEAR_DOUBLE: "clear.wav",
    GameEvent.CLEAR_TRIPLE: "clear.wav",
    GameEvent.CLEAR_KENJIRI: "kenjiri.wav",  # whistle REPLACES the pop (D26)
    GameEvent.LEVEL_UP: "levelup.wav",    # excited bark fanfare
    GameEvent.TOP_OUT: "gameover.wav",    # sad puppy whine
    GameEvent.HOLD_USED: "menu.wav",      # menu blip
    UiSound.MENU: "menu.wav",
}


def project_root() -> Path:
    """Return the repository root in a dev run (parent of ``src/``)."""
    return Path(__file__).resolve().parents[3]


def assets_dir() -> Path:
    """Resolve the ``assets/`` directory for dev runs AND the packaged exe.

    PyInstaller onefile unpacks bundled data to ``sys._MEIPASS``; dev runs
    fall back to the repository root (the committed assets are canonical,
    D28).
    """
    base = Path(getattr(sys, "_MEIPASS", project_root()))
    return base / "assets"


class Audio:
    """The Kenjiri audio engine (interface contract + D12/D24/D26).

    Construct once at app start; call :meth:`tick` once per logic frame to
    drive delayed SFX and duck recovery. When the mixer or the asset files
    are unavailable, the instance stays disabled and every call is a no-op
    (D24: run silent, never crash).
    """

    def __init__(self) -> None:
        """Initialise the mixer and load every SFX; degrade silently on
        failure (D24, logged once)."""
        self._enabled = False
        self._sounds: dict[Enum, pygame.mixer.Sound] = {}
        self._channels: dict[str, pygame.mixer.Channel] = {}
        self._pending: list[tuple[Enum, int]] = []
        self._duck_left = 0
        self._paused = False
        self._current_track: str | None = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            sfx_dir = assets_dir() / "sfx"
            loaded: dict[str, pygame.mixer.Sound] = {}
            for filename in sorted(set(_SFX_FILES.values())):
                loaded[filename] = pygame.mixer.Sound(str(sfx_dir / filename))
            # One dedicated channel per distinct sample: re-triggering a
            # sound restarts it instead of stacking (D12: never stack-clip).
            pygame.mixer.set_num_channels(max(8, len(loaded)))
            for index, filename in enumerate(sorted(loaded)):
                self._channels[filename] = pygame.mixer.Channel(index)
            self._sounds = {
                event: loaded[filename] for event, filename in _SFX_FILES.items()
            }
            self._enabled = True
        except (pygame.error, FileNotFoundError, OSError) as exc:
            _logger.warning("audio unavailable; running silent (D24): %s", exc)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """True when the mixer initialised and all samples loaded."""
        return self._enabled

    # ------------------------------------------------------------------ SFX

    def play(self, event: GameEvent | UiSound) -> None:
        """Play the SFX mapped to *event* (no-op when silent or unmapped).

        Any SFX ducks the music to 60% volume, recovering linearly over
        250 ms (D26).
        """
        if not self._enabled:
            return
        sound = self._sounds.get(event)
        if sound is None:
            return  # unmapped events (e.g. SPAWN) are silent by design
        self._channels[_SFX_FILES[event]].play(sound)
        self._duck_left = DUCK_FRAMES
        self._apply_music_volume()

    def play_later(self, event: GameEvent | UiSound, delay_frames: int) -> None:
        """Queue *event*'s SFX to play after *delay_frames* logic frames
        (D12: whistle -> bark fanfare 300 ms later)."""
        if not self._enabled:
            return
        self._pending.append((event, max(1, delay_frames)))

    def duration_frames(self, event: GameEvent | UiSound) -> int:
        """Return *event*'s sample length in logic frames (0 when silent)."""
        if not self._enabled:
            return 0
        sound = self._sounds.get(event)
        if sound is None:
            return 0
        return int(sound.get_length() * FPS) + 1

    def tick(self) -> None:
        """Advance one logic frame: fire due delayed SFX, recover the duck."""
        if not self._enabled:
            return
        if self._pending:
            still_pending: list[tuple[Enum, int]] = []
            for event, frames_left in self._pending:
                if frames_left <= 1:
                    self.play(event)  # type: ignore[arg-type]
                else:
                    still_pending.append((event, frames_left - 1))
            self._pending = still_pending
        if self._duck_left > 0:
            self._duck_left -= 1
            self._apply_music_volume()

    # ---------------------------------------------------------------- music

    def music(self, track: str) -> None:
        """Start *track* (``title`` | ``gameplay`` | ``gameover``).

        Title and gameplay loop seamlessly (D11); the game-over theme plays
        once (D23). Raises ``ValueError`` for an unknown track name — that
        is a programming error, not a degraded mode.
        """
        if track not in MUSIC_TRACKS:
            raise ValueError(f"unknown music track {track!r}")
        if not self._enabled:
            return
        filename, loops = MUSIC_TRACKS[track]
        try:
            pygame.mixer.music.load(str(assets_dir() / "music" / filename))
            self._apply_music_volume()
            pygame.mixer.music.play(loops)
            self._current_track = track
        except (pygame.error, FileNotFoundError, OSError) as exc:
            _logger.warning("music %r failed; running silent (D24): %s", track, exc)

    def set_paused(self, paused: bool) -> None:
        """Apply/lift the pause music attenuation (-50%, D23)."""
        self._paused = paused
        if self._enabled:
            self._apply_music_volume()

    # ------------------------------------------------------------- internal

    def _apply_music_volume(self) -> None:
        """Combine the pause factor with the duck envelope (D23/D26)."""
        duck = DUCK_FLOOR + (1.0 - DUCK_FLOOR) * (1.0 - self._duck_left / DUCK_FRAMES)
        base = PAUSE_MUSIC_FACTOR if self._paused else 1.0
        try:
            pygame.mixer.music.set_volume(base * duck)
        except pygame.error:  # mixer torn down mid-call — stay silent (D24)
            pass
