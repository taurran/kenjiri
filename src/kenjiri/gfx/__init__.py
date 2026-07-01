"""kenjiri.gfx — palette-indexed pixel art, pixel font, and particles (T3).

All sprites are authored as in-code string grids (no external images) and
rendered to per-pixel-alpha ``pygame.Surface`` objects. Nothing in this
package touches the display, so it is safe under ``SDL_VIDEODRIVER=dummy``.
"""

from kenjiri.gfx.font import render
from kenjiri.gfx.palette import PALETTE, PIECE_KEYS
from kenjiri.gfx.particles import DustPuff, SparkleBurst
from kenjiri.gfx.sprites import (
    MascotState,
    block,
    corgi_title,
    logo,
    mascot,
    piece_glyph,
)

__all__ = [
    "PALETTE",
    "PIECE_KEYS",
    "MascotState",
    "block",
    "corgi_title",
    "logo",
    "mascot",
    "piece_glyph",
    "render",
    "DustPuff",
    "SparkleBurst",
]
