"""Kenjiri sprites — all pixel art as palette-indexed string grids in code.

No external image files (frozen plan, T3): every sprite is authored as rows
of characters, each character indexing a :data:`~kenjiri.gfx.palette.PALETTE`
key, and rendered onto a per-pixel-alpha ``pygame.Surface`` via ``set_at``.

Builders (interface contract):
- :func:`block` — 8x8 piece tile with NES-style bevel + white spark (D10).
- :func:`piece_glyph` — 4-cell miniature for the HUD STATISTICS panel (D8).
- :func:`logo` — chunky striped "KENJIRI" NES-style wordmark (D9).
- :func:`corgi_title` — 48x48 chibi title-screen corgi (D9).
- :func:`mascot` — 24x24 corner mascot, 4 emote states x 2 frames (D14).

Nothing here touches the display: surfaces are created headless-safe
(``SRCALPHA``, no ``convert_alpha``), so tests run under the dummy driver.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Mapping, Sequence

import pygame

from kenjiri.gfx.palette import PALETTE, PIECE_KEYS

__all__ = [
    "MascotState",
    "block",
    "corgi_title",
    "logo",
    "mascot",
    "piece_glyph",
    "surface_from_grid",
]


class MascotState(Enum):
    """Corner-mascot emote states (D14)."""

    IDLE = auto()   # tail wag loop
    HAPPY = auto()  # line clear — smile + bounce
    HYPE = auto()   # Kenjiri / level-up — ears up, sparkle eyes
    SAD = auto()    # top-out — droopy ears


# Character -> palette key used by all string-grid art in this module.
_CHAR_COLORS: dict[str, str] = {
    "o": "CORGI_ORANGE",
    "c": "CORGI_CREAM",
    "w": "WHITE",
    "k": "OUTLINE",
    "r": "COLLAR",
    "p": "TONGUE",
    "a": "I",  # soft-aqua accent (mascot tear / sparkle tint)
    "y": "O",  # butter-yellow accent (hype sparkles)
}


def surface_from_grid(
    grid: Sequence[str],
    size: tuple[int, int] | None = None,
    char_colors: Mapping[str, str] | None = None,
) -> pygame.Surface:
    """Render a string grid to a per-pixel-alpha surface.

    ``.`` (and space) are transparent; every other character must map to a
    palette key via *char_colors*. Rows shorter than the surface width are
    padded transparent; rows longer than the width are an authoring error.
    """
    colors = _CHAR_COLORS if char_colors is None else char_colors
    width = size[0] if size else max(len(row) for row in grid)
    height = size[1] if size else len(grid)
    if len(grid) > height:
        raise ValueError(f"grid has {len(grid)} rows, surface height {height}")
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        if len(row) > width:
            raise ValueError(f"row {y} is {len(row)} chars, surface width {width}")
        for x, ch in enumerate(row):
            if ch in (".", " "):
                continue
            if ch not in colors:
                raise ValueError(f"unmapped art character {ch!r} at {(x, y)}")
            surf.set_at((x, y), (*PALETTE[colors[ch]], 255))
    return surf


# --------------------------------------------------------------------- blocks

def block(kind: str) -> pygame.Surface:
    """8x8 field tile for *kind* with an NES-style bevel.

    Light edge top-left, dark edge bottom-right, single white spark pixel —
    all colors straight from :data:`PALETTE` (palette-scan safe).
    """
    if kind not in PIECE_KEYS:
        raise KeyError(f"unknown piece kind {kind!r}")
    base = PALETTE[kind]
    light = PALETTE[f"{kind}_LIGHT"]
    dark = PALETTE[f"{kind}_DARK"]
    surf = pygame.Surface((8, 8), pygame.SRCALPHA)
    surf.fill((*base, 255))
    for i in range(8):
        surf.set_at((i, 0), (*light, 255))   # top edge
        surf.set_at((i, 7), (*dark, 255))    # bottom edge
    for i in range(7):
        surf.set_at((0, i), (*light, 255))   # left edge (light wins top-left)
    for i in range(1, 8):
        surf.set_at((7, i), (*dark, 255))    # right edge (dark wins bottom-right)
    surf.set_at((1, 1), (*PALETTE["WHITE"], 255))  # spark
    return surf


# --------------------------------------------------------------------- glyphs

# Flat-side-down miniature footprints (cells in a small grid), per piece kind.
_GLYPH_CELLS: dict[str, tuple[tuple[int, int], ...]] = {
    "I": ((0, 0), (1, 0), (2, 0), (3, 0)),
    "O": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "T": ((1, 0), (0, 1), (1, 1), (2, 1)),
    "S": ((1, 0), (2, 0), (0, 1), (1, 1)),
    "Z": ((0, 0), (1, 0), (1, 1), (2, 1)),
    "J": ((0, 0), (0, 1), (1, 1), (2, 1)),
    "L": ((2, 0), (0, 1), (1, 1), (2, 1)),
}

_GLYPH_CELL_PX = 2


def piece_glyph(kind: str) -> pygame.Surface:
    """Small 4-cell miniature of *kind* for the HUD STATISTICS panel (D8)."""
    cells = _GLYPH_CELLS[kind]
    width = (max(x for x, _ in cells) + 1) * _GLYPH_CELL_PX
    height = (max(y for _, y in cells) + 1) * _GLYPH_CELL_PX
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    color = (*PALETTE[kind], 255)
    for cx, cy in cells:
        for dx in range(_GLYPH_CELL_PX):
            for dy in range(_GLYPH_CELL_PX):
                surf.set_at((cx * _GLYPH_CELL_PX + dx, cy * _GLYPH_CELL_PX + dy), color)
    return surf


# ----------------------------------------------------------------------- logo

# Chunky 6x7 letterforms for the wordmark (thicker strokes than the HUD font).
_LOGO_GLYPHS: dict[str, tuple[str, ...]] = {
    "K": (
        "XX..XX",
        "XX.XX.",
        "XXXX..",
        "XXX...",
        "XXXX..",
        "XX.XX.",
        "XX..XX",
    ),
    "E": (
        "XXXXXX",
        "XX....",
        "XX....",
        "XXXXX.",
        "XX....",
        "XX....",
        "XXXXXX",
    ),
    "N": (
        "XX..XX",
        "XXX.XX",
        "XXXXXX",
        "XXXXXX",
        "XX.XXX",
        "XX..XX",
        "XX..XX",
    ),
    "J": (
        "XXXXXX",
        "..XX..",
        "..XX..",
        "..XX..",
        "..XX..",
        "XXXX..",
        ".XX...",
    ),
    "I": (
        "XXXXXX",
        "..XX..",
        "..XX..",
        "..XX..",
        "..XX..",
        "..XX..",
        "XXXXXX",
    ),
    "R": (
        "XXXXX.",
        "XX..XX",
        "XX..XX",
        "XXXXX.",
        "XXXX..",
        "XX.XX.",
        "XX..XX",
    ),
}

# Horizontal stripe colors by glyph row — multi-color like the NES Tetris logo.
_LOGO_STRIPES: tuple[str, ...] = (
    "WARM_ORANGE",
    "WARM_ORANGE",
    "PINK",
    "PINK",
    "CREAM",
    "UI_MINT",
    "UI_MINT",
)

_LOGO_TEXT = "KENJIRI"


def logo() -> pygame.Surface:
    """Chunky striped "KENJIRI" wordmark (D9), 2x scaled, with drop shadow."""
    glyph_w, glyph_h = 6, 7
    spacing = 1
    width = len(_LOGO_TEXT) * (glyph_w + spacing) - spacing + 1  # +1 shadow
    height = glyph_h + 1  # +1 shadow
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    shadow = (*PALETTE["OUTLINE"], 255)
    for index, letter in enumerate(_LOGO_TEXT):
        rows = _LOGO_GLYPHS[letter]
        left = index * (glyph_w + spacing)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != "X":
                    continue
                surf.set_at((left + x + 1, y + 1), shadow)  # drop shadow first
        for y, row in enumerate(rows):
            stripe = (*PALETTE[_LOGO_STRIPES[y]], 255)
            for x, ch in enumerate(row):
                if ch != "X":
                    continue
                surf.set_at((left + x, y), stripe)
    return pygame.transform.scale(surf, (width * 2, height * 2))


# ---------------------------------------------------------------- title corgi

# 48x48 chibi corgi: big head, tall ears with cream inner, white blaze,
# kawaii eyes with sparkle, cream muzzle, tongue out, collar, cream chest,
# white paw tips. Corgis have docked tails — none needed here.
_CORGI_TITLE: tuple[str, ...] = (
    "..........kk........................kk..........",
    ".........kook......................kook.........",
    "........koook......................koook........",
    ".......koocck......................kccook.......",
    "......koocccck....................kccccook......",
    ".....koocccccck..................kccccccook.....",
    ".....koooccccck...kkkkkkkkkkkk...kcccccoook.....",
    ".....kooooooooooooooooooooooooooooooooooook.....",
    "....kooooooooooooooooowwwwoooooooooooooooook....",
    "...koooooooooooooooooowwwwooooooooooooooooook...",
    "...koooooooooooooooooowwwwooooooooooooooooook...",
    "..kooooooooooooooooooowwwwoooooooooooooooooook..",
    "..kooooooooooooooooooowwwwoooooooooooooooooook..",
    "..kooooooooooooooooooowwwwoooooooooooooooooook..",
    "..kooooooooooooooooooowwwwoooooooooooooooooook..",
    "..kooooooooooooooooooowwwwoooooooooooooooooook..",
    "..kooooooooookkkkoooowwwwwwooookkkkooooooooook..",
    "..kooooooooookwkkoooowwwwwwooookkwkooooooooook..",
    "..kooooooooookkkkoooowwwwwwooookkkkooooooooook..",
    "..kooooooooookkkkoooowwwwwwooookkkkooooooooook..",
    "..koooooooooooooccccccccccccccccoooooooooooook..",
    "..kooooooooooooocccccckkkkccccccoooooooooooook..",
    "..kooooooooooooocccccckkkkccccccoooooooooooook..",
    "..koooooooooooooccccccckkcccccccoooooooooooook..",
    "..kooooooooooooocccckkkkkkkkccccoooooooooooook..",
    "..koooooooooooooccccckppppkcccccoooooooooooook..",
    "...kooooooooooooccccckppppkcccccooooooooooook...",
    "....koooooooooooccccckppppkcccccoooooooooook....",
    ".....koooooooooocccccckkkkccccccooooooooook.....",
    "......kooooooookkkkkkkkkkkkkkkkkkooooooook......",
    ".............krrrrrrrrrrrrrrrrrrrrk.............",
    "...........kooooooccccccccccccooooook...........",
    "..........kooooooccccccccccccccooooook..........",
    ".........koooooooccccccccccccccoooooook.........",
    "........kooooooooccccccccccccccooooooook........",
    "........kooooooooccccccccccccccooooooook........",
    ".......koooooooooccccccccccccccoooooooook.......",
    "......kooooooooooccccccccccccccooooooooook......",
    "......kooooooooooccccccccccccccooooooooook......",
    "......kooooooooooccccccccccccccooooooooook......",
    "......kooooooooooccccccccccccccooooooooook......",
    "......kooooooooooccccooooooccccooooooooook......",
    "......kooooooooooccccooooooccccooooooooook......",
    "......kooooooooooccccooooooccccooooooooook......",
    "......koooooooooowwwwoooooowwwwooooooooook......",
    "......koooooooooowwwwoooooowwwwooooooooook......",
    ".......kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk.......",
    "................................................",
)


def corgi_title() -> pygame.Surface:
    """The 48x48 chibi pixel corgi for the title screen (D9)."""
    return surface_from_grid(_CORGI_TITLE, size=(48, 48))


# --------------------------------------------------------------------- mascot

def _patch(grid: Sequence[str], patches: Mapping[int, str]) -> tuple[str, ...]:
    """Return *grid* with the rows in *patches* replaced (frame variants)."""
    return tuple(patches.get(i, row) for i, row in enumerate(grid))


def _shift_up(grid: Sequence[str]) -> tuple[str, ...]:
    """Return *grid* moved up one pixel (bounce frame)."""
    return tuple(list(grid[1:]) + ["." * len(grid[0])])


# Base 24x24 mascot: upright ears with cream inner, white blaze, sparkle
# eyes, cream muzzle with tongue, collar, cream chest, white paw tips, and
# a stubby tail nub at the right (rows 17-18 — wag swings it up in IDLE f1).
_MASCOT_BASE: tuple[str, ...] = (
    "....kk............kk....",
    "...kook..........kook...",
    "..kocck..........kccok..",
    "..kooookkkkkkkkkkooook..",
    ".kooooooooooooooooooook.",
    "kooooooooowwwwoooooooook",
    "kooooooooowwwwoooooooook",
    "koookwkooowwwwoookwkoook",
    "koookkkooowwwwoookkkoook",
    "kooooooccccccccccooooook",
    "kooooooccckkkkcccooooook",
    "koooooocccckkccccooooook",
    "kooooooccccppccccooooook",
    ".koooooookkkkkkoooooook.",
    "...krrrrrrrrrrrrrrrrk...",
    "..koooccccccccccccoook..",
    ".kooooccccccccccccooook.",
    ".kooooccccccccccccooooko",
    ".kooooccccccccccccooooko",
    ".koooooccccccccccoooook.",
    ".kooooocccoooocccoooook.",
    ".kooooocccoooocccoooook.",
    ".kooooowwwoooowwwoooook.",
    "..kkkkkkkkkkkkkkkkkkkk..",
)

# --- frame variants -------------------------------------------------------

# IDLE: tail wag — the nub swings from low (base, rows 17-18) to high.
_IDLE_0 = _MASCOT_BASE
_IDLE_1 = _patch(
    _MASCOT_BASE,
    {
        15: "..koooccccccccccccoook.o",
        16: ".kooooccccccccccccooooko",
        17: ".kooooccccccccccccooook.",
        18: ".kooooccccccccccccooook.",
    },
)

# HAPPY: closed happy eye-arcs (ink over the coat) + open tongue smile;
# frame 1 bounces the whole pup up one pixel.
_HAPPY_0 = _patch(
    _MASCOT_BASE,
    {
        7: "kooookoooowwwwooookooook",
        8: "koookokooowwwwoookokoook",
        11: "kooooooccckppkcccooooook",
        12: "kooooooccckppkcccooooook",
    },
)
_HAPPY_1 = _shift_up(_HAPPY_0)

# HYPE: ears fully perked (broad tips), starry sparkle eyes, butter-yellow
# sparks that alternate corners between frames.
_HYPE_0 = _patch(
    _MASCOT_BASE,
    {
        0: "...kkkk..........kkkk..y",
        2: "y.kocck..........kccok..",
        7: "kooowwwooowwwwooowwwoook",
        8: "koookwkooowwwwoookwkoook",
    },
)
_HYPE_1 = _patch(
    _MASCOT_BASE,
    {
        0: "y..kkkk..........kkkk...",
        2: "..kocck..........kccok.y",
        7: "koookwkooowwwwoookwkoook",
        8: "kooowkwooowwwwooowkwoook",
    },
)

# SAD: upright ears gone, droopy flaps at the sides, lowered lids (only the
# lower eye line remains), mouth fallen to a flat frown; frame 1 adds an
# aqua tear below the left eye. Tail stays still.
_SAD_0 = _patch(
    _MASCOT_BASE,
    {
        0: "........................",
        1: "........................",
        2: "..kk................kk..",
        3: ".kook..kkkkkkkkkk..kook.",
        7: "kooooooooowwwwoooooooook",
        11: "kooooooccccccccccooooook",
        12: "kooooooccckkkkcccooooook",
    },
)
_SAD_1 = _patch(
    _SAD_0,
    {
        9: "koooaooccccccccccooooook",
        10: "koooaooccckkkkcccooooook",
    },
)

_MASCOT_FRAMES: dict[MascotState, tuple[tuple[str, ...], tuple[str, ...]]] = {
    MascotState.IDLE: (_IDLE_0, _IDLE_1),
    MascotState.HAPPY: (_HAPPY_0, _HAPPY_1),
    MascotState.HYPE: (_HYPE_0, _HYPE_1),
    MascotState.SAD: (_SAD_0, _SAD_1),
}


def mascot(state: MascotState, frame: int) -> pygame.Surface:
    """24x24 corner-mascot sprite for *state*, animation *frame* (mod 2)."""
    grid = _MASCOT_FRAMES[state][frame % 2]
    return surface_from_grid(grid, size=(24, 24))
