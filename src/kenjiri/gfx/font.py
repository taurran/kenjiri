"""Kenjiri 5x7 pixel font.

Glyphs: digits 0-9, A-Z, space, and the punctuation set ``! . - × : /``.
Each glyph is a 7-row, 5-column string grid ('X' = ink, '.' = transparent).
:func:`render` draws text onto a fresh per-pixel-alpha surface with 1px
letter spacing; an unknown character raises ``KeyError`` (fail loud, D17
spirit — the HUD must never silently drop characters).
"""

from __future__ import annotations

from typing import Sequence

import pygame

__all__ = ["GLYPHS", "GLYPH_WIDTH", "GLYPH_HEIGHT", "LETTER_SPACING", "render"]

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
LETTER_SPACING = 1

GLYPHS: dict[str, tuple[str, ...]] = {
    "0": (".XXX.", "X...X", "X..XX", "X.X.X", "XX..X", "X...X", ".XXX."),
    "1": ("..X..", ".XX..", "..X..", "..X..", "..X..", "..X..", ".XXX."),
    "2": (".XXX.", "X...X", "....X", "...X.", "..X..", ".X...", "XXXXX"),
    "3": ("XXXXX", "....X", "...X.", "..XX.", "....X", "X...X", ".XXX."),
    "4": ("...X.", "..XX.", ".X.X.", "X..X.", "XXXXX", "...X.", "...X."),
    "5": ("XXXXX", "X....", "XXXX.", "....X", "....X", "X...X", ".XXX."),
    "6": ("..XX.", ".X...", "X....", "XXXX.", "X...X", "X...X", ".XXX."),
    "7": ("XXXXX", "....X", "...X.", "..X..", ".X...", ".X...", ".X..."),
    "8": (".XXX.", "X...X", "X...X", ".XXX.", "X...X", "X...X", ".XXX."),
    "9": (".XXX.", "X...X", "X...X", ".XXXX", "....X", "...X.", ".XX.."),
    "A": (".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"),
    "B": ("XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."),
    "C": (".XXX.", "X...X", "X....", "X....", "X....", "X...X", ".XXX."),
    "D": ("XXXX.", "X...X", "X...X", "X...X", "X...X", "X...X", "XXXX."),
    "E": ("XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"),
    "F": ("XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "X...."),
    "G": (".XXX.", "X...X", "X....", "X.XXX", "X...X", "X...X", ".XXXX"),
    "H": ("X...X", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"),
    "I": (".XXX.", "..X..", "..X..", "..X..", "..X..", "..X..", ".XXX."),
    "J": ("..XXX", "...X.", "...X.", "...X.", "...X.", "X..X.", ".XX.."),
    "K": ("X...X", "X..X.", "X.X..", "XX...", "X.X..", "X..X.", "X...X"),
    "L": ("X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"),
    "M": ("X...X", "XX.XX", "X.X.X", "X.X.X", "X...X", "X...X", "X...X"),
    "N": ("X...X", "XX..X", "X.X.X", "X..XX", "X...X", "X...X", "X...X"),
    "O": (".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "P": ("XXXX.", "X...X", "X...X", "XXXX.", "X....", "X....", "X...."),
    "Q": (".XXX.", "X...X", "X...X", "X...X", "X.X.X", "X..X.", ".XX.X"),
    "R": ("XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"),
    "S": (".XXXX", "X....", "X....", ".XXX.", "....X", "....X", "XXXX."),
    "T": ("XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."),
    "U": ("X...X", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "V": ("X...X", "X...X", "X...X", "X...X", "X...X", ".X.X.", "..X.."),
    "W": ("X...X", "X...X", "X...X", "X.X.X", "X.X.X", "XX.XX", "X...X"),
    "X": ("X...X", "X...X", ".X.X.", "..X..", ".X.X.", "X...X", "X...X"),
    "Y": ("X...X", "X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."),
    "Z": ("XXXXX", "....X", "...X.", "..X..", ".X...", "X....", "XXXXX"),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "!": ("..X..", "..X..", "..X..", "..X..", "..X..", ".....", "..X.."),
    ".": (".....", ".....", ".....", ".....", ".....", ".XX..", ".XX.."),
    "-": (".....", ".....", ".....", ".XXX.", ".....", ".....", "....."),
    "×": (".....", "X...X", ".X.X.", "..X..", ".X.X.", "X...X", "....."),
    ":": (".....", ".XX..", ".XX..", ".....", ".XX..", ".XX..", "....."),
    "/": ("....X", "...X.", "...X.", "..X..", ".X...", ".X...", "X...."),
}


def render(text: str, color: Sequence[int]) -> pygame.Surface:
    """Render *text* in *color* onto a new per-pixel-alpha surface.

    Letters are 5x7 with 1px spacing. Raises ``KeyError`` for characters
    without a glyph.
    """
    if not text:
        return pygame.Surface((0, GLYPH_HEIGHT), pygame.SRCALPHA)
    rgba = (int(color[0]), int(color[1]), int(color[2]), 255)
    width = len(text) * GLYPH_WIDTH + (len(text) - 1) * LETTER_SPACING
    surf = pygame.Surface((width, GLYPH_HEIGHT), pygame.SRCALPHA)
    for index, ch in enumerate(text):
        rows = GLYPHS[ch]
        left = index * (GLYPH_WIDTH + LETTER_SPACING)
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell == "X":
                    surf.set_at((left + x, y), rgba)
    return surf
