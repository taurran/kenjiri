"""Kenjiri scenes: title, gameplay (with pause + game over) (D4/D9/D20/D21/D23/D26).

Scene protocol (driven by :class:`kenjiri.ui.app.App`):

- ``enter()`` — called once when the scene becomes current (starts music).
- ``handle_event(event)`` — pygame input events.
- ``update()`` — advance exactly ONE 60 fps logic frame.
- ``draw(canvas)`` — render onto the 256x240 internal canvas.
- ``auto_pause()`` — D28 focus-loss/stall hook; only the gameplay scene
  reacts (title and game-over hold no time-sensitive state).

Controls per D4 verbatim: ←/→ shift; ↓ soft drop; ↑ or X rotate CW; Z or
Ctrl rotate CCW; Space hard drop; C or Shift hold; P or Esc pause; Enter =
confirm on menus. Esc on the title screen exits the app (D26).
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol

import pygame

from kenjiri.audio.engine import LEVEL_UP_DELAY_FRAMES, UiSound
from kenjiri.game.inputmap import Action, InputFrame, make_frame
from kenjiri.game.state import ActivePiece, Game, GameEvent
from kenjiri.gfx import font, sprites
from kenjiri.gfx.palette import PALETTE, PIECE_KEYS
from kenjiri.gfx.particles import DustPuff, SparkleBurst
from kenjiri.gfx.sprites import MascotState
from kenjiri.ui import hud as hud_mod
from kenjiri.ui.hud import CANVAS_SIZE, FIELD_ORIGIN, FIELD_SIZE, Hud

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cycle
    from kenjiri.audio.engine import Audio
    from kenjiri.persistence.highscore import HighScoreStore

__all__ = ["AppServices", "GameplayScene", "TitleScene"]

# --- D4 key map: pygame key -> input action -------------------------------
KEY_ACTIONS: dict[int, Action] = {
    pygame.K_LEFT: "left",
    pygame.K_RIGHT: "right",
    pygame.K_DOWN: "soft_drop",
    pygame.K_UP: "rotate_cw",
    pygame.K_x: "rotate_cw",
    pygame.K_z: "rotate_ccw",
    pygame.K_LCTRL: "rotate_ccw",
    pygame.K_RCTRL: "rotate_ccw",
    pygame.K_SPACE: "hard_drop",
    pygame.K_c: "hold",
    pygame.K_LSHIFT: "hold",
    pygame.K_RSHIFT: "hold",
}

#: Level-driven (held-state) actions suppressed on resume so DAS cannot
#: slide the piece after unpausing (D4/D23) — until the key is re-pressed.
_RESUME_SUPPRESSED_ACTIONS: frozenset[Action] = frozenset(
    {"left", "right", "soft_drop"}
)

_PAUSE_KEYS = (pygame.K_p, pygame.K_ESCAPE)
_CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER)

# --- timing constants (60 fps reference frames) ----------------------------
TITLE_BLINK_FRAMES = 30
"""PUSH START blink half-period (D9)."""

KENJIRI_POP_FRAMES = 36
"""'KENJIRI!' text pop duration: 0.6 s (D23)."""

CLEAR_FLASH_PERIOD = 3
"""White-flash alternation during the clear animation (D23)."""

MASCOT_HAPPY_FRAMES = 60
"""HAPPY emote hold on line clears: ~1 s (D14)."""

MASCOT_HYPE_FRAMES = 90
"""HYPE emote hold on Kenjiri/level-up: ~1.5 s (D14)."""

MASCOT_IDLE_WAG_FRAMES = 30
"""IDLE tail wag at ~2 animation frames/s (D14)."""

MASCOT_EMOTE_ANIM_FRAMES = 10
"""Non-idle emotes animate faster for liveliness."""

FIELD_DIM_ALPHA = 153
"""Pause dims the field 60% (D23): 0.6 * 255."""


class AppServices(Protocol):
    """What scenes need from the app shell (duck-typed to avoid a cycle)."""

    @property
    def audio(self) -> "Audio":
        """The shared audio engine."""

    @property
    def store(self) -> "HighScoreStore":
        """The shared high-score store."""

    def switch(self, scene: object) -> None:
        """Make *scene* current (calls its ``enter()``)."""

    def quit(self) -> None:
        """Shut the app down cleanly."""


def _held_actions(down_keys: set[int]) -> frozenset[Action]:
    """Map currently-down pygame keys to the set of held input actions."""
    return frozenset(
        KEY_ACTIONS[key] for key in down_keys if key in KEY_ACTIONS
    )


class TitleScene:
    """Title screen (D9/D20/D26): logo, chibi corgi, blinking PUSH START.

    Enter/Space/click starts gameplay at level 0 (D20); Esc exits the app
    (D26). The title theme loops while the scene is up.
    """

    def __init__(self, app: AppServices) -> None:
        """Bind to the app services and pre-render static art."""
        self._app = app
        self._frame = 0
        self._logo = sprites.logo()
        self._corgi = sprites.corgi_title()
        self._border: pygame.Surface | None = None

    def enter(self) -> None:
        """Start the looping title theme (D9/D11)."""
        self._app.audio.music("title")

    def auto_pause(self) -> None:
        """No-op: only the gameplay scene auto-pauses (D28)."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """Enter/Space/click -> start at level 0; Esc -> exit app (D26)."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._app.quit()
            elif event.key in _CONFIRM_KEYS or event.key == pygame.K_SPACE:
                self._start()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._start()

    def _start(self) -> None:
        """Begin a fresh run at level 0 (D20) with a menu blip."""
        self._app.audio.play(UiSound.MENU)
        self._app.switch(GameplayScene(self._app))

    def update(self) -> None:
        """Advance the blink counter and the audio engine."""
        self._frame += 1
        self._app.audio.tick()

    def draw(self, canvas: pygame.Surface) -> None:
        """Render logo + corgi + blinking PUSH START inside a brick border."""
        canvas.fill(PALETTE["FIELD_BG"])
        canvas.blit(self._brick_border(), (0, 0))
        canvas.blit(self._logo, ((CANVAS_SIZE[0] - self._logo.get_width()) // 2, 40))
        canvas.blit(
            self._corgi, ((CANVAS_SIZE[0] - self._corgi.get_width()) // 2, 88)
        )
        if (self._frame // TITLE_BLINK_FRAMES) % 2 == 0:
            prompt = font.render("PUSH START", PALETTE["CREAM"])
            canvas.blit(prompt, ((CANVAS_SIZE[0] - prompt.get_width()) // 2, 168))

    def _brick_border(self) -> pygame.Surface:
        """Tetromino-brick border around the canvas edge (D9), cached."""
        if self._border is None:
            surf = pygame.Surface(CANVAS_SIZE, pygame.SRCALPHA)
            tiles = [sprites.block(kind) for kind in PIECE_KEYS]
            width, height = CANVAS_SIZE
            index = 0
            for x in range(0, width, 8):
                surf.blit(tiles[index % len(tiles)], (x, 0))
                surf.blit(tiles[(index + 3) % len(tiles)], (x, height - 8))
                index += 1
            for y in range(8, height - 8, 8):
                surf.blit(tiles[index % len(tiles)], (0, y))
                surf.blit(tiles[(index + 3) % len(tiles)], (width - 8, y))
                index += 1
            self._border = surf
        return self._border


class GameplayScene:
    """The playable game: Game + HUD + particles + mascot + pause/game-over.

    One :meth:`update` call = exactly one logic frame = exactly one
    ``Game.step(InputFrame)`` (frozen plan). Pause (D23) freezes the game,
    particles and animations; Q from pause abandons the run unpersisted
    (D26). Top-out submits the score (persist point, D21) and shows the
    game-over panel (D23).
    """

    def __init__(self, app: AppServices) -> None:
        """Create a fresh run at level 0 with an empty Field."""
        self._app = app
        self._game = Game(random.Random())
        self._hud = Hud()
        self._particle_rng = random.Random()
        self._particles: list[SparkleBurst | DustPuff] = []
        self._down_keys: set[int] = set()
        self._prev_held: frozenset[Action] = frozenset()
        self._suppressed: set[Action] = set()
        self._paused = False
        self._over = False
        self._new_top = False
        self._frame = 0
        self._mascot_state = MascotState.IDLE
        self._mascot_frames_left = 0  # 0 with IDLE/SAD = no pending revert
        self._kenjiri_pop_left = 0
        self._gameover_music_in: int | None = None

    # ------------------------------------------------------------ properties

    @property
    def paused(self) -> bool:
        """True while the PAWSED panel is up (D23)."""
        return self._paused

    @property
    def game_over(self) -> bool:
        """True once the run topped out (D25)."""
        return self._over

    # ---------------------------------------------------------------- events

    def enter(self) -> None:
        """Start the looping gameplay theme (D11)."""
        self._app.audio.music("gameplay")

    def auto_pause(self) -> None:
        """D28: auto-pause on focus loss/minimize or a >250 ms stall."""
        if not self._paused and not self._over:
            self._set_paused(True, blip=False)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route input per D4/D23/D26 (see module docstring)."""
        if event.type == pygame.KEYUP:
            self._down_keys.discard(event.key)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self._over:
            if event.key in _CONFIRM_KEYS:
                self._app.audio.play(UiSound.MENU)
                self._app.switch(TitleScene(self._app))
            return
        if event.key in _PAUSE_KEYS:
            self._set_paused(not self._paused, blip=True)
            return
        if self._paused:
            if event.key == pygame.K_q:
                # Q abandons the run — score NOT persisted (D26/D21).
                self._app.audio.set_paused(False)
                self._app.audio.play(UiSound.MENU)
                self._app.switch(TitleScene(self._app))
            return
        if event.key in KEY_ACTIONS:
            self._down_keys.add(event.key)

    def _set_paused(self, paused: bool, blip: bool) -> None:
        """Enter/leave pause: music -50% (D23); DAS cleared on resume (D4).

        On resume, currently-held shift/soft-drop keys are suppressed until
        re-pressed, so the next InputFrames carry no held state for them —
        the game's DAS charge resets and the piece cannot slide.
        """
        self._paused = paused
        self._app.audio.set_paused(paused)
        if not paused:
            self._suppressed = set(
                _held_actions(self._down_keys) & _RESUME_SUPPRESSED_ACTIONS
            )
        if blip:
            self._app.audio.play(UiSound.MENU)

    # ---------------------------------------------------------------- update

    def update(self) -> None:
        """Advance one logic frame (game, particles, timers, audio)."""
        self._app.audio.tick()
        if self._paused:
            return  # gravity, DAS, lock delay AND animations frozen (D23)
        self._frame += 1
        self._update_particles()
        if self._kenjiri_pop_left > 0:
            self._kenjiri_pop_left -= 1
        self._update_mascot_timer()
        if self._gameover_music_in is not None:
            self._gameover_music_in -= 1
            if self._gameover_music_in <= 0:
                self._gameover_music_in = None
                self._app.audio.music("gameover")  # plays once (D23)
        if self._over:
            return
        pre_active = self._game.active
        frame = self._build_input_frame()
        events = self._game.step(frame)
        if events:
            self._handle_game_events(events, pre_active)

    def _build_input_frame(self) -> InputFrame:
        """Sample held keys into an InputFrame (edges vs the previous
        frame; resume suppression per D4)."""
        raw = _held_actions(self._down_keys)
        self._suppressed &= raw  # a released key ends its suppression
        effective = raw - self._suppressed
        frame = make_frame(effective, self._prev_held)
        self._prev_held = effective
        return frame

    def _update_particles(self) -> None:
        """Advance emitters one frame and drop the finished ones."""
        if not self._particles:
            return
        for emitter in self._particles:
            emitter.update(1)
        self._particles = [p for p in self._particles if p.alive]

    def _update_mascot_timer(self) -> None:
        """Count a temporary emote down and revert to IDLE (SAD is sticky)."""
        if self._mascot_frames_left > 0:
            self._mascot_frames_left -= 1
            if self._mascot_frames_left == 0:
                self._mascot_state = MascotState.IDLE

    # --------------------------------------------------------- event wiring

    def _handle_game_events(
        self, events: list[GameEvent], pre_active: ActivePiece | None
    ) -> None:
        """Wire this frame's game events to SFX/particles/mascot (D12/D13/D26)."""
        audio = self._app.audio
        hard_dropped = GameEvent.HARD_DROP in events
        if hard_dropped:
            audio.play(GameEvent.HARD_DROP)
            self._spawn_dust_puff(pre_active)
        if GameEvent.LOCK in events:
            audio.play(GameEvent.LOCK)

        clear_event = next(
            (
                e
                for e in events
                if e
                in (
                    GameEvent.CLEAR_SINGLE,
                    GameEvent.CLEAR_DOUBLE,
                    GameEvent.CLEAR_TRIPLE,
                    GameEvent.CLEAR_KENJIRI,
                )
            ),
            None,
        )
        if clear_event is not None:
            audio.play(clear_event)  # whistle REPLACES the pop on a quad (D26)
            self._spawn_sparkles()
            if clear_event is GameEvent.CLEAR_KENJIRI:
                self._kenjiri_pop_left = KENJIRI_POP_FRAMES  # 0.6 s (D23)
                self._set_mascot(MascotState.HYPE, MASCOT_HYPE_FRAMES)
            else:
                self._set_mascot(MascotState.HAPPY, MASCOT_HAPPY_FRAMES)

        if GameEvent.LEVEL_UP in events:
            if clear_event is GameEvent.CLEAR_KENJIRI:
                # D12: whistle plays, bark fanfare follows 300 ms later.
                audio.play_later(GameEvent.LEVEL_UP, LEVEL_UP_DELAY_FRAMES)
            else:
                audio.play(GameEvent.LEVEL_UP)
            self._set_mascot(MascotState.HYPE, MASCOT_HYPE_FRAMES)

        if GameEvent.HOLD_USED in events:
            audio.play(GameEvent.HOLD_USED)

        if GameEvent.TOP_OUT in events:
            self._on_top_out()

    def _on_top_out(self) -> None:
        """Top-out: whine, sad mascot, persist the score (D21/D23)."""
        audio = self._app.audio
        audio.play(GameEvent.TOP_OUT)  # sad puppy whine (D12)
        self._set_mascot(MascotState.SAD, sticky=True)
        game = self._game
        pre_top = self._app.store.top()
        self._app.store.submit(game.score, game.lines, game.level)
        # "NEW TOP!" = the record was beaten this run — compare against the
        # pre-submit TOP (session-only mode returns False from submit()).
        self._new_top = game.score > pre_top
        self._over = True
        # Whine first, then the game-over theme once (D23).
        self._gameover_music_in = max(1, audio.duration_frames(GameEvent.TOP_OUT))

    def _set_mascot(
        self, state: MascotState, frames: int = 0, sticky: bool = False
    ) -> None:
        """Switch the mascot emote; SAD is sticky until the scene ends."""
        if self._mascot_state is MascotState.SAD:
            return  # sad is sticky (D14)
        self._mascot_state = state
        self._mascot_frames_left = 0 if sticky else frames

    # ------------------------------------------------------------- particles

    def _spawn_dust_puff(self, pre_active: ActivePiece | None) -> None:
        """Dust puff at the hard-drop landing row (D13)."""
        if pre_active is None:
            return
        landing = pre_active.ghost_cells or pre_active.cells
        visible = [(c, r) for c, r in landing if r <= 20]
        if not visible:
            return
        bottom_row = min(r for _, r in visible)
        mean_col = sum(c for c, _ in visible) / len(visible)
        center = hud_mod.cell_center(round(mean_col), bottom_row)
        self._particles.append(DustPuff(center, self._particle_rng))

    def _spawn_sparkles(self) -> None:
        """Sparkle bursts along every clearing row (D13/D23)."""
        for row in self._game.clearing or ():
            if row > 20:
                continue  # Buffer rows render nothing (D25)
            for col in (3, 8):
                self._particles.append(
                    SparkleBurst(hud_mod.cell_center(col, row), self._particle_rng)
                )

    # ------------------------------------------------------------------ draw

    def draw(self, canvas: pygame.Surface) -> None:
        """Render HUD, field, particles and any pause/game-over overlay."""
        canvas.fill(PALETTE["OUTLINE"])
        flash_on = (
            self._game.clearing is not None
            and (self._frame // CLEAR_FLASH_PERIOD) % 2 == 0
        )
        display_top = max(self._app.store.top(), self._game.score)  # live TOP (D21)
        self._hud.draw(
            canvas,
            self._game,
            display_top,
            self._mascot_state,
            self._mascot_anim_frame(),
            flash_on,
        )
        for emitter in self._particles:
            emitter.draw(canvas)
        if self._kenjiri_pop_left > 0:
            self._draw_kenjiri_pop(canvas)
        if self._paused:
            self._draw_pause_panel(canvas)
        if self._over:
            self._draw_game_over_panel(canvas)

    def _mascot_anim_frame(self) -> int:
        """Animation frame index: idle wags at ~2 frames/s (D14)."""
        period = (
            MASCOT_IDLE_WAG_FRAMES
            if self._mascot_state is MascotState.IDLE
            else MASCOT_EMOTE_ANIM_FRAMES
        )
        return self._frame // period

    def _draw_kenjiri_pop(self, canvas: pygame.Surface) -> None:
        """'KENJIRI!' pixel text pops center-field for 0.6 s (D13/D23)."""
        color = (
            PALETTE["O"]
            if (self._kenjiri_pop_left // 6) % 2 == 0
            else PALETTE["WHITE"]
        )
        rendered = font.render("KENJIRI!", color)
        text = pygame.transform.scale(
            rendered, (rendered.get_width() * 2, rendered.get_height() * 2)
        )
        canvas.blit(
            text,
            (
                FIELD_ORIGIN[0] + (FIELD_SIZE[0] - text.get_width()) // 2,
                FIELD_ORIGIN[1] + (FIELD_SIZE[1] - text.get_height()) // 2,
            ),
        )

    def _dim_field(self, canvas: pygame.Surface) -> None:
        """Dim the playfield 60% (D23)."""
        overlay = pygame.Surface(FIELD_SIZE, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, FIELD_DIM_ALPHA))
        canvas.blit(overlay, FIELD_ORIGIN)

    def _draw_pause_panel(self, canvas: pygame.Surface) -> None:
        """PAWSED panel over the dimmed field (D23/D26)."""
        self._dim_field(canvas)
        panel = pygame.Rect(33, 96, 190, 52)
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], panel)
        pygame.draw.rect(canvas, PALETTE["PINK"], panel, 1)
        title = font.render("PAWSED", PALETTE["CREAM"])
        title = pygame.transform.scale(
            title, (title.get_width() * 2, title.get_height() * 2)
        )
        canvas.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 7))
        self._draw_paw(canvas, panel.centerx - title.get_width() // 2 - 14, panel.y + 9)
        # "P/ESC RESUME · Q QUIT TO TITLE" (D26) — the middle dot is drawn
        # as pixels (the 5x7 font has no '·' glyph).
        left = font.render("P/ESC RESUME", PALETTE["TEXT"])
        right = font.render("Q QUIT TO TITLE", PALETTE["TEXT"])
        total = left.get_width() + 3 + 2 + 3 + right.get_width()
        x = panel.centerx - total // 2
        y = panel.y + 32
        canvas.blit(left, (x, y))
        dot_x = x + left.get_width() + 3
        pygame.draw.rect(canvas, PALETTE["TEXT"], (dot_x, y + 2, 2, 2))
        canvas.blit(right, (dot_x + 2 + 3, y))

    @staticmethod
    def _draw_paw(canvas: pygame.Surface, x: int, y: int) -> None:
        """Tiny pixel paw print next to the PAWSED title (D23)."""
        color = PALETTE["PINK"]
        pygame.draw.rect(canvas, color, (x + 2, y + 4, 5, 4))  # pad
        for dx, dy in ((0, 0), (3, -2), (6, 0)):
            pygame.draw.rect(canvas, color, (x + dx, y + dy, 2, 2))  # toes

    def _draw_game_over_panel(self, canvas: pygame.Surface) -> None:
        """Game-over panel: SCORE/LINES/LEVEL, TOP, NEW TOP! banner (D23/D21)."""
        self._dim_field(canvas)
        game = self._game
        panel = pygame.Rect(70, 68, 116, 110)
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], panel)
        pygame.draw.rect(canvas, PALETTE["WARM_ORANGE"], panel, 1)
        title = font.render("GAME OVER", PALETTE["Z"])
        canvas.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 8))
        rows: list[tuple[str, str]] = [
            ("SCORE", f"{game.score:07d}"),
            ("LINES", f"{min(game.lines, 9999):04d}"),
            ("LEVEL", f"{game.level:02d}"),
            ("TOP", f"{max(self._app.store.top(), game.score):07d}"),
        ]
        y = panel.y + 24
        for label, value in rows:
            canvas.blit(font.render(label, PALETTE["CREAM"]), (panel.x + 8, y))
            surf = font.render(value, PALETTE["TEXT"])
            canvas.blit(surf, (panel.right - 8 - surf.get_width(), y))
            y += 12
        if self._new_top and (self._frame // TITLE_BLINK_FRAMES) % 2 == 0:
            banner = font.render("NEW TOP!", PALETTE["O"])
            canvas.blit(banner, (panel.centerx - banner.get_width() // 2, y + 2))
        hint = font.render("ENTER: TITLE", PALETTE["TEXT_DIM"])
        canvas.blit(
            hint, (panel.centerx - hint.get_width() // 2, panel.bottom - 14)
        )
