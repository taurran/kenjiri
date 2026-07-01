"""Kenjiri pastel palette (frozen decision D10).

D10 verbatim: "Pastel versions of standard piece hues: I soft-aqua, L peach,
J periwinkle, S mint, Z blush-rose, O butter-yellow, T lavender;
cream/warm-orange/pink/mint UI framing; bright, chibi, Japanese-kawaii tone."

Every color the gfx layer paints comes from :data:`PALETTE` so sprites stay
cohesive and the palette-scan test can prove no stray colors sneak in.
Piece colors are chosen bright (high luminance) so 8x8 blocks read clearly
against the deep warm-dark field background (``FIELD_BG``).
"""

from __future__ import annotations

Color = tuple[int, int, int]

#: Canonical piece order for the gfx layer (matches game-side PieceKind).
PIECE_KEYS: tuple[str, ...] = ("I", "O", "T", "S", "Z", "J", "L")


def _mix(color: Color, other: Color, amount: float) -> Color:
    """Blend *color* toward *other* by *amount* (0.0 keeps color, 1.0 = other)."""
    return (
        round(color[0] + (other[0] - color[0]) * amount),
        round(color[1] + (other[1] - color[1]) * amount),
        round(color[2] + (other[2] - color[2]) * amount),
    )


def lighten(color: Color, amount: float = 0.45) -> Color:
    """Pastel-lighten *color* toward white for NES bevel top-left edges."""
    return _mix(color, (255, 255, 255), amount)


def darken(color: Color, amount: float = 0.35) -> Color:
    """Deepen *color* toward the field dark for NES bevel bottom-right edges."""
    return _mix(color, (24, 18, 28), amount)


# D10 piece hues — bright kawaii pastels, distinct at 8x8 on a dark field.
_PIECE_BASE: dict[str, Color] = {
    "I": (137, 226, 225),  # soft aqua
    "O": (250, 223, 133),  # butter yellow
    "T": (203, 166, 235),  # lavender
    "S": (155, 227, 168),  # mint
    "Z": (241, 156, 170),  # blush rose
    "J": (154, 163, 238),  # periwinkle
    "L": (250, 190, 140),  # peach
}

PALETTE: dict[str, Color] = {
    # --- UI framing per D10: cream / warm-orange / pink / mint ---
    "CREAM": (247, 239, 218),
    "WARM_ORANGE": (235, 154, 92),
    "PINK": (244, 178, 199),
    "UI_MINT": (176, 226, 196),
    # --- text / dim / ghost / field ---
    "TEXT": (252, 250, 242),
    "TEXT_DIM": (169, 158, 176),
    "GHOST": (120, 108, 132),
    "FIELD_BG": (34, 28, 40),  # deep warm-dark playfield
    # --- shared sprite ink ---
    "WHITE": (255, 255, 255),
    "OUTLINE": (56, 42, 58),
    # --- corgi coat + accessories (D9/D14) ---
    "CORGI_ORANGE": (232, 152, 84),
    "CORGI_CREAM": (248, 230, 202),
    "COLLAR": (216, 90, 106),
    "TONGUE": (240, 134, 154),
}

for _kind, _rgb in _PIECE_BASE.items():
    PALETTE[_kind] = _rgb
    PALETTE[f"{_kind}_LIGHT"] = lighten(_rgb)
    PALETTE[f"{_kind}_DARK"] = darken(_rgb)
