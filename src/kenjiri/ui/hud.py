"""Kenjiri gameplay HUD (D8/D19/D21/D23/D26) on the 256x240 canvas.

Layout per D8 (SNES reference, pastel corgi recolor from PALETTE):

- Left panel: STATISTICS — all 7 piece glyphs with running spawn counters
  (display capped at 999, D8).
- Top-center: LINES-NNN — grows to 4 digits past 999, display clamps at
  9999 while the internal counter keeps counting (D26).
- Right column, top to bottom: NEXT box (1 piece, D19), HOLD box directly
  below it (dashed outline when empty; the stashed glyph greyed ~40% while
  hold is unavailable, D19), TOP + SCORE (7 digits, D7), LEVEL.
- Mascot panel bottom-right (D23).
- Playfield center 10x20: deep warm-dark background, ghost cells in the
  GHOST palette color (D25), Buffer rows 21-22 NEVER rendered.

TOP updates live when the current score exceeds it (D21) — the scene passes
the already-maxed display value in.
"""
from __future__ import annotations

import pygame

from kenjiri.game import pieces
from kenjiri.game.board import VISIBLE_ROWS
from kenjiri.game.state import Game
from kenjiri.gfx import font, sprites
from kenjiri.gfx.palette import PALETTE, PIECE_KEYS, Color
from kenjiri.gfx.sprites import MascotState

__all__ = ["Hud", "CANVAS_SIZE", "FIELD_ORIGIN", "FIELD_SIZE", "cell_topleft", "cell_center"]

CANVAS_SIZE = (256, 240)
"""The internal NES-resolution canvas (D16)."""

CELL_PX = 8
"""Field cell size in canvas pixels (8x8 block tiles)."""

FIELD_COLS = 10
FIELD_ORIGIN = (88, 48)
"""Top-left canvas pixel of the visible Field (10x20 centered, D8)."""

FIELD_SIZE = (FIELD_COLS * CELL_PX, VISIBLE_ROWS * CELL_PX)
"""Visible Field size in pixels: 80x160."""

STATS_DISPLAY_CAP = 999
"""STATISTICS counters cap at 999 on screen (D8)."""

LINES_DISPLAY_CAP = 9999
"""LINES display clamps at 9999; the counter keeps counting (D26)."""

SCORE_DIGITS = 7
"""Score/TOP show 7 digits, matching the 9,999,999 cap (D7)."""

# Right-column geometry (canvas px).
_RIGHT_X = 188
_BOX_W, _BOX_H = 52, 26
_NEXT_LABEL_Y, _NEXT_BOX_Y = 36, 44
_HOLD_LABEL_Y, _HOLD_BOX_Y = 74, 82
_TOP_LABEL_Y, _TOP_VALUE_Y = 114, 123
_SCORE_LABEL_Y, _SCORE_VALUE_Y = 136, 145
_LEVEL_LABEL_Y, _LEVEL_VALUE_Y = 160, 169
_MASCOT_PANEL = pygame.Rect(194, 192, 40, 40)

# Left statistics panel geometry.
_STATS_PANEL = pygame.Rect(4, 44, 80, 148)
_STATS_TITLE_Y = 48
_STATS_ROW_Y0 = 62
_STATS_ROW_STEP = 18

_LINES_PANEL = pygame.Rect(86, 6, 84, 18)

_HOLD_GREY_ALPHA = 153  # ~40% greyed while hold is unavailable (D19)


def cell_topleft(col: int, row: int) -> tuple[int, int]:
    """Canvas pixel of the top-left corner of Field cell ``(col, row)``.

    Matrix coordinates per D25: columns 1-10 left-to-right, rows bottom-up;
    only rows 1-20 are visible.
    """
    return (
        FIELD_ORIGIN[0] + (col - 1) * CELL_PX,
        FIELD_ORIGIN[1] + (VISIBLE_ROWS - row) * CELL_PX,
    )


def cell_center(col: int, row: int) -> tuple[int, int]:
    """Canvas pixel of the center of Field cell ``(col, row)``."""
    x, y = cell_topleft(col, row)
    return (x + CELL_PX // 2, y + CELL_PX // 2)


class Hud:
    """Draws the full gameplay HUD onto the internal canvas.

    Caches block tiles, glyphs and rendered text so the per-frame cost is
    blits, not ``set_at`` loops.
    """

    def __init__(self) -> None:
        """Build and cache the per-kind block tiles, glyphs and previews."""
        self._blocks: dict[str, pygame.Surface] = {
            kind: sprites.block(kind) for kind in PIECE_KEYS
        }
        self._glyphs: dict[str, pygame.Surface] = {
            kind: sprites.piece_glyph(kind) for kind in PIECE_KEYS
        }
        self._previews: dict[str, pygame.Surface] = {
            kind: self._build_preview(kind) for kind in PIECE_KEYS
        }
        self._text_cache: dict[tuple[str, Color], pygame.Surface] = {}

    # ------------------------------------------------------------- text

    def text(self, message: str, color: Color) -> pygame.Surface:
        """Render (and cache) *message* in the 5x7 pixel font."""
        key = (message, color)
        cached = self._text_cache.get(key)
        if cached is None:
            if len(self._text_cache) > 512:
                self._text_cache.clear()
            cached = font.render(message, color)
            self._text_cache[key] = cached
        return cached

    # ------------------------------------------------------------- draw

    def draw(
        self,
        canvas: pygame.Surface,
        game: Game,
        top_score: int,
        mascot_state: MascotState,
        mascot_frame: int,
        clear_flash_on: bool,
    ) -> None:
        """Draw the complete HUD + Field for one frame.

        Args:
            canvas: The 256x240 internal canvas.
            game: The game to render.
            top_score: The TOP value to display (already live-maxed with the
                current score by the scene, D21).
            mascot_state: Current mascot emote (D14).
            mascot_frame: Mascot animation frame index.
            clear_flash_on: True on white-flash frames of the line-clear
                animation (D23).
        """
        self._draw_lines_panel(canvas, game.lines)
        self._draw_field(canvas, game, clear_flash_on)
        self._draw_statistics(canvas, game.piece_counts)
        self._draw_right_column(canvas, game, top_score)
        self._draw_mascot(canvas, mascot_state, mascot_frame)

    # ---------------------------------------------------------- internals

    def _build_preview(self, kind: str) -> pygame.Surface:
        """Full-size (8px block) preview of *kind* in its spawn rotation,
        for the NEXT/HOLD boxes (D19)."""
        cells = pieces.CELLS[kind][0]
        min_x = min(dx for dx, _ in cells)
        max_x = max(dx for dx, _ in cells)
        min_y = min(dy for _, dy in cells)
        max_y = max(dy for _, dy in cells)
        surf = pygame.Surface(
            ((max_x - min_x + 1) * CELL_PX, (max_y - min_y + 1) * CELL_PX),
            pygame.SRCALPHA,
        )
        for dx, dy in cells:
            surf.blit(
                self._blocks[kind],
                ((dx - min_x) * CELL_PX, (max_y - dy) * CELL_PX),
            )
        return surf

    def _draw_lines_panel(self, canvas: pygame.Surface, lines: int) -> None:
        """Top-center LINES-NNN (D8), 4-digit reflow past 999, clamp 9999
        (D26)."""
        if lines <= 999:
            message = f"LINES-{lines:03d}"
        else:
            message = f"LINES-{min(lines, LINES_DISPLAY_CAP):04d}"
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], _LINES_PANEL)
        pygame.draw.rect(canvas, PALETTE["CREAM"], _LINES_PANEL, 1)
        surf = self.text(message, PALETTE["TEXT"])
        canvas.blit(
            surf,
            (
                _LINES_PANEL.centerx - surf.get_width() // 2,
                _LINES_PANEL.centery - surf.get_height() // 2,
            ),
        )

    def _draw_field(
        self, canvas: pygame.Surface, game: Game, clear_flash_on: bool
    ) -> None:
        """Playfield: dark background, locked cells, clear flash, ghost,
        active piece. Buffer rows 21-22 are NEVER rendered (D25)."""
        field_rect = pygame.Rect(FIELD_ORIGIN, FIELD_SIZE)
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], field_rect)
        pygame.draw.rect(canvas, PALETTE["CREAM"], field_rect.inflate(2, 2), 1)

        clearing = set(game.clearing or ())
        board = game.board
        for row in range(1, VISIBLE_ROWS + 1):
            flash_row = clear_flash_on and row in clearing
            for col in range(1, FIELD_COLS + 1):
                kind = board.cell(col, row)
                if kind is None:
                    continue
                pos = cell_topleft(col, row)
                if flash_row:
                    pygame.draw.rect(
                        canvas, PALETTE["WHITE"], (*pos, CELL_PX, CELL_PX)
                    )
                else:
                    canvas.blit(self._blocks[kind], pos)

        active = game.active
        if active is None:
            return
        if active.ghost_cells is not None:
            for col, row in active.ghost_cells:
                if row > VISIBLE_ROWS:
                    continue
                pygame.draw.rect(
                    canvas, PALETTE["GHOST"], (*cell_topleft(col, row), CELL_PX, CELL_PX), 1
                )
        for col, row in active.cells:
            if row > VISIBLE_ROWS:
                continue  # Buffer cells render nothing (D25)
            canvas.blit(self._blocks[active.kind], cell_topleft(col, row))

    def _draw_statistics(
        self, canvas: pygame.Surface, counts: dict[str, int]
    ) -> None:
        """Left STATISTICS panel: 7 piece glyphs + spawn counters (D8)."""
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], _STATS_PANEL)
        pygame.draw.rect(canvas, PALETTE["WARM_ORANGE"], _STATS_PANEL, 1)
        title = self.text("STATISTICS", PALETTE["PINK"])
        canvas.blit(
            title, (_STATS_PANEL.centerx - title.get_width() // 2, _STATS_TITLE_Y)
        )
        for index, kind in enumerate(PIECE_KEYS):
            y = _STATS_ROW_Y0 + index * _STATS_ROW_STEP
            glyph = self._glyphs[kind]
            canvas.blit(glyph, (_STATS_PANEL.x + 8, y + (8 - glyph.get_height()) // 2))
            value = self.text(
                f"{min(counts.get(kind, 0), STATS_DISPLAY_CAP):03d}", PALETTE["TEXT"]
            )
            canvas.blit(value, (_STATS_PANEL.right - 8 - value.get_width(), y))

    def _draw_right_column(
        self, canvas: pygame.Surface, game: Game, top_score: int
    ) -> None:
        """NEXT box, HOLD box directly below, TOP + SCORE, LEVEL (D8/D19)."""
        # NEXT (1 piece, D19).
        canvas.blit(self.text("NEXT", PALETTE["CREAM"]), (_RIGHT_X, _NEXT_LABEL_Y))
        next_box = pygame.Rect(_RIGHT_X, _NEXT_BOX_Y, _BOX_W, _BOX_H)
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], next_box)
        pygame.draw.rect(canvas, PALETTE["UI_MINT"], next_box, 1)
        self._blit_centered(canvas, self._previews[game.next_kind], next_box)

        # HOLD directly below NEXT (D19).
        canvas.blit(self.text("HOLD", PALETTE["CREAM"]), (_RIGHT_X, _HOLD_LABEL_Y))
        hold_box = pygame.Rect(_RIGHT_X, _HOLD_BOX_Y, _BOX_W, _BOX_H)
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], hold_box)
        if game.hold_kind is None:
            self._draw_dashed_rect(canvas, hold_box, PALETTE["TEXT_DIM"])
        else:
            pygame.draw.rect(canvas, PALETTE["UI_MINT"], hold_box, 1)
            preview = self._previews[game.hold_kind]
            if not game.hold_available:
                preview = preview.copy()
                preview.set_alpha(_HOLD_GREY_ALPHA)  # greyed ~40% (D19)
            self._blit_centered(canvas, preview, hold_box)

        # TOP + SCORE (7 digits, D7/D21) and LEVEL.
        canvas.blit(self.text("TOP", PALETTE["WARM_ORANGE"]), (_RIGHT_X, _TOP_LABEL_Y))
        canvas.blit(
            self.text(f"{top_score:0{SCORE_DIGITS}d}", PALETTE["TEXT"]),
            (_RIGHT_X, _TOP_VALUE_Y),
        )
        canvas.blit(self.text("SCORE", PALETTE["CREAM"]), (_RIGHT_X, _SCORE_LABEL_Y))
        canvas.blit(
            self.text(f"{game.score:0{SCORE_DIGITS}d}", PALETTE["TEXT"]),
            (_RIGHT_X, _SCORE_VALUE_Y),
        )
        canvas.blit(self.text("LEVEL", PALETTE["CREAM"]), (_RIGHT_X, _LEVEL_LABEL_Y))
        canvas.blit(
            self.text(f"{game.level:02d}", PALETTE["TEXT"]),
            (_RIGHT_X, _LEVEL_VALUE_Y),
        )

    def _draw_mascot(
        self, canvas: pygame.Surface, state: MascotState, frame: int
    ) -> None:
        """Mascot panel, bottom-right corner below LEVEL (D14/D23)."""
        pygame.draw.rect(canvas, PALETTE["FIELD_BG"], _MASCOT_PANEL)
        pygame.draw.rect(canvas, PALETTE["PINK"], _MASCOT_PANEL, 1)
        sprite = sprites.mascot(state, frame)
        self._blit_centered(canvas, sprite, _MASCOT_PANEL)

    @staticmethod
    def _blit_centered(
        canvas: pygame.Surface, surf: pygame.Surface, box: pygame.Rect
    ) -> None:
        """Blit *surf* centered inside *box*."""
        canvas.blit(
            surf,
            (
                box.centerx - surf.get_width() // 2,
                box.centery - surf.get_height() // 2,
            ),
        )

    @staticmethod
    def _draw_dashed_rect(
        canvas: pygame.Surface, box: pygame.Rect, color: Color
    ) -> None:
        """Dashed 1px outline — the empty HOLD box affordance (D19)."""
        dash, gap = 3, 3
        step = dash + gap
        for x in range(box.left, box.right, step):
            width = min(dash, box.right - x)
            pygame.draw.line(canvas, color, (x, box.top), (x + width - 1, box.top))
            pygame.draw.line(
                canvas, color, (x, box.bottom - 1), (x + width - 1, box.bottom - 1)
            )
        for y in range(box.top, box.bottom, step):
            height = min(dash, box.bottom - y)
            pygame.draw.line(canvas, color, (box.left, y), (box.left, y + height - 1))
            pygame.draw.line(
                canvas, color, (box.right - 1, y), (box.right - 1, y + height - 1)
            )
