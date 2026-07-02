"""Acceptance tests for T3 — kenjiri.gfx (palette, sprites, font, particles).

Covers the frozen PLAN acceptance criteria:
- every PieceKind has a block tile and a HUD glyph;
- all mascot state/frame combos render; logo and corgi render non-empty at
  expected sizes; font renders "KENJIRI 1200 PAWSED" without KeyError;
- particle emitters produce per-pixel-alpha surfaces and decay to zero
  particles within a bounded frame count;
- NEGATIVE: gfx modules never touch the display (no set_mode), and every
  non-transparent pixel used by block sprites is a PALETTE value.
"""

from __future__ import annotations

import random
from pathlib import Path

import pygame
import pytest

from kenjiri.gfx import font, palette, particles, sprites
from kenjiri.gfx.palette import PALETTE, PIECE_KEYS
from kenjiri.gfx.sprites import MascotState

KINDS = ("I", "O", "T", "S", "Z", "J", "L")

UI_KEYS = (
    "CREAM",
    "WARM_ORANGE",
    "PINK",
    "UI_MINT",
    "TEXT",
    "TEXT_DIM",
    "GHOST",
    "FIELD_BG",
    "WHITE",
    "OUTLINE",
    "CORGI_ORANGE",
    "CORGI_CREAM",
    "COLLAR",
    "TONGUE",
)


def _opaque(surf: pygame.Surface) -> list[tuple[int, int, pygame.Color]]:
    """All pixels of *surf* with alpha > 0, as (x, y, color) triples."""
    w, h = surf.get_size()
    return [
        (x, y, surf.get_at((x, y)))
        for y in range(h)
        for x in range(w)
        if surf.get_at((x, y)).a > 0
    ]


# ---------------------------------------------------------------- palette

def test_palette_has_all_piece_and_ui_colors() -> None:
    assert PIECE_KEYS == KINDS
    for key in KINDS + UI_KEYS:
        assert key in PALETTE, f"missing palette key {key!r}"
    for kind in KINDS:
        assert f"{kind}_LIGHT" in PALETTE
        assert f"{kind}_DARK" in PALETTE


def test_palette_values_are_rgb_triples() -> None:
    for key, value in PALETTE.items():
        assert isinstance(value, tuple) and len(value) == 3, key
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in value), key


def test_palette_piece_colors_distinct_and_pastel_bright() -> None:
    bases = [PALETTE[k] for k in KINDS]
    assert len(set(bases)) == 7, "piece colors must be distinct"
    field = PALETTE["FIELD_BG"]
    assert sum(field) < 180, "field background must be a deep dark"
    for kind in KINDS:
        assert sum(PALETTE[kind]) > 420, f"{kind} must read bright on dark field"


# ---------------------------------------------------------------- blocks

@pytest.mark.parametrize("kind", KINDS)
def test_block_is_8x8_and_fully_opaque(kind: str) -> None:
    surf = sprites.block(kind)
    assert surf.get_size() == (8, 8)
    assert len(_opaque(surf)) == 64


@pytest.mark.parametrize("kind", KINDS)
def test_block_has_nes_bevel_and_spark(kind: str) -> None:
    surf = sprites.block(kind)
    assert tuple(surf.get_at((0, 0)))[:3] == PALETTE[f"{kind}_LIGHT"]
    assert tuple(surf.get_at((7, 7)))[:3] == PALETTE[f"{kind}_DARK"]
    colors = {tuple(c)[:3] for _, _, c in _opaque(surf)}
    assert PALETTE["WHITE"] in colors, "missing white spark pixel"
    assert PALETTE[kind] in colors, "missing base body color"


@pytest.mark.parametrize("kind", KINDS)
def test_block_colors_all_within_palette(kind: str) -> None:
    """NEGATIVE: no color outside PALETTE is used by block sprites."""
    allowed = set(PALETTE.values())
    for x, y, c in _opaque(sprites.block(kind)):
        assert tuple(c)[:3] in allowed, f"off-palette pixel at {(x, y)}: {tuple(c)}"


# ---------------------------------------------------------------- glyphs

@pytest.mark.parametrize("kind", KINDS)
def test_piece_glyph_has_exactly_four_cells(kind: str) -> None:
    surf = sprites.piece_glyph(kind)
    # 4 cells at 2x2 px each
    assert len(_opaque(surf)) == 16


def test_piece_glyph_shapes_unique() -> None:
    footprints = set()
    for kind in KINDS:
        surf = sprites.piece_glyph(kind)
        footprints.add(
            (surf.get_size(), frozenset((x, y) for x, y, _ in _opaque(surf)))
        )
    assert len(footprints) == 7


# ---------------------------------------------------------------- logo / corgi

def test_logo_renders_striped_wordmark() -> None:
    surf = sprites.logo()
    px = _opaque(surf)
    assert px, "logo is empty"
    assert surf.get_width() > surf.get_height(), "wordmark should be wide"
    assert surf.get_height() >= 14
    colors = {tuple(c)[:3] for _, _, c in px}
    assert len(colors) >= 4, "logo must be multi-color striped (NES style)"


def test_corgi_title_renders_48x48_chibi() -> None:
    surf = sprites.corgi_title()
    assert surf.get_size() == (48, 48)
    px = _opaque(surf)
    assert len(px) >= 300, "corgi should fill a healthy chunk of its canvas"
    colors = {tuple(c)[:3] for _, _, c in px}
    for key in ("CORGI_ORANGE", "CORGI_CREAM", "COLLAR", "TONGUE", "WHITE"):
        assert PALETTE[key] in colors, f"corgi missing {key} pixels"


# ---------------------------------------------------------------- mascot

@pytest.mark.parametrize("state", list(MascotState))
@pytest.mark.parametrize("frame", [0, 1])
def test_mascot_every_state_frame_renders(state: MascotState, frame: int) -> None:
    surf = sprites.mascot(state, frame)
    assert surf.get_size() == (24, 24)
    assert len(_opaque(surf)) >= 40


@pytest.mark.parametrize("state", list(MascotState))
def test_mascot_frames_animate(state: MascotState) -> None:
    f0 = pygame.image.tobytes(sprites.mascot(state, 0), "RGBA")
    f1 = pygame.image.tobytes(sprites.mascot(state, 1), "RGBA")
    assert f0 != f1, f"{state} frames must differ (2-frame animation)"


def test_mascot_states_are_distinct() -> None:
    frames = {
        state: pygame.image.tobytes(sprites.mascot(state, 0), "RGBA")
        for state in MascotState
    }
    assert len(set(frames.values())) == len(MascotState)


def test_mascot_frame_wraps_modulo() -> None:
    a = pygame.image.tobytes(sprites.mascot(MascotState.IDLE, 0), "RGBA")
    b = pygame.image.tobytes(sprites.mascot(MascotState.IDLE, 2), "RGBA")
    assert a == b


# ---------------------------------------------------------------- font

def test_font_renders_required_hud_string() -> None:
    surf = font.render("KENJIRI 1200 PAWSED", PALETTE["TEXT"])
    n = len("KENJIRI 1200 PAWSED")
    assert surf.get_size() == (n * 5 + (n - 1), 7)
    assert _opaque(surf)


def test_font_covers_digits_letters_punctuation() -> None:
    for ch in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ!.-×:/":
        surf = font.render(ch, PALETTE["TEXT"])
        assert surf.get_size() == (5, 7)
        assert _opaque(surf), f"glyph {ch!r} rendered empty"


def test_font_applies_requested_color() -> None:
    color = PALETTE["WARM_ORANGE"]
    surf = font.render("SCORE:1200", color)
    for x, y, c in _opaque(surf):
        assert tuple(c)[:3] == color


def test_font_unknown_char_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        font.render("@", PALETTE["TEXT"])


# ---------------------------------------------------------------- particles

def test_sparkle_burst_deterministic_with_injected_rng() -> None:
    a = particles.SparkleBurst((10, 10), random.Random(7))
    b = particles.SparkleBurst((10, 10), random.Random(7))
    a.update(5)
    b.update(5)
    assert [(p.x, p.y, p.age, p.color) for p in a.particles] == [
        (p.x, p.y, p.age, p.color) for p in b.particles
    ]


def test_sparkle_burst_draws_with_alpha_then_decays() -> None:
    burst = particles.SparkleBurst((32, 32), random.Random(3))
    assert burst.alive and burst.particle_count > 0
    target = pygame.Surface((64, 64), pygame.SRCALPHA)
    burst.update(2)
    burst.draw(target)
    assert any(
        target.get_at((x, y)).a > 0 for x in range(64) for y in range(64)
    ), "sparkles drew nothing"
    burst.update(120)
    assert burst.particle_count == 0 and not burst.alive, "sparkles must decay"


def test_dust_puff_is_translucent_and_decays() -> None:
    puff = particles.DustPuff((32, 60), random.Random(11))
    puff.update(3)
    target = pygame.Surface((64, 72), pygame.SRCALPHA)
    puff.draw(target)
    alphas = {
        target.get_at((x, y)).a for x in range(64) for y in range(72)
    }
    assert any(0 < a < 255 for a in alphas), "dust puff must be translucent"
    puff.update(120)
    assert puff.particle_count == 0 and not puff.alive, "dust must fade out"


def test_particles_draw_respects_offset() -> None:
    a = particles.DustPuff((8, 8), random.Random(5))
    b = particles.DustPuff((8, 8), random.Random(5))
    a.update(1)
    b.update(1)
    t1 = pygame.Surface((64, 64), pygame.SRCALPHA)
    t2 = pygame.Surface((64, 64), pygame.SRCALPHA)
    a.draw(t1)
    b.draw(t2, offset=(20, 20))
    assert pygame.image.tobytes(t1, "RGBA") != pygame.image.tobytes(t2, "RGBA")


# ---------------------------------------------------------------- negatives

def test_gfx_modules_never_call_set_mode() -> None:
    """NEGATIVE: gfx must stay display-free (headless/merge safety)."""
    for mod in (palette, sprites, font, particles):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "set_mode" not in source, f"{mod.__name__} touches the display"


def test_all_builders_work_with_display_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """NEGATIVE: every builder runs while set_mode is booby-trapped."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("gfx code must never open a display")

    monkeypatch.setattr(pygame.display, "set_mode", _boom)
    for kind in KINDS:
        sprites.block(kind)
        sprites.piece_glyph(kind)
    sprites.logo()
    sprites.corgi_title()
    for state in MascotState:
        sprites.mascot(state, 0)
        sprites.mascot(state, 1)
    font.render("KENJIRI 1200 PAWSED ×2 A/B:C-D!", PALETTE["TEXT"])
    burst = particles.SparkleBurst((5, 5), random.Random(1))
    puff = particles.DustPuff((5, 5), random.Random(2))
    burst.update(1)
    puff.update(1)
    target = pygame.Surface((16, 16), pygame.SRCALPHA)
    burst.draw(target)
    puff.draw(target)
