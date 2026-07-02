"""Kenjiri particles (frozen decision D13).

D13: "Star/sparkle burst on clearing blocks during the ~0.3 s clear
animation; transparent dust puff at landing row on hard drop; ... Per-pixel-
alpha surfaces in pygame."

Two emitters, both deterministic given an injected ``random.Random``:

- :class:`SparkleBurst` — pastel star/plus sparks that pop outward from a
  cleared block and twinkle out (plus-shape alternating with a single pixel).
- :class:`DustPuff` — soft translucent blobs that expand, drift up and fade,
  for the hard-drop landing thud.

``update(frames)`` is pure logic (no pygame calls); ``draw(surface, offset)``
paints with per-pixel alpha via ``set_at``/temp-``SRCALPHA`` blits, never
touching the display.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from kenjiri.gfx.palette import PALETTE, Color

__all__ = ["DustPuff", "SparkleBurst"]

# Pastel spark tints — sampled per particle at spawn.
_SPARK_COLORS: tuple[Color, ...] = (
    PALETTE["WHITE"],
    PALETTE["I"],
    PALETTE["O"],
    PALETTE["Z"],
    PALETTE["T"],
)

_PLUS_OFFSETS: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class _Spark:
    """One sparkle: position, velocity, age and tint."""

    x: float
    y: float
    vx: float
    vy: float
    age: int
    life: int
    color: Color


class SparkleBurst:
    """Star sparks popping outward from *center*, twinkling out (D13)."""

    def __init__(
        self,
        center: tuple[int, int],
        rng: random.Random,
        count: int = 14,
    ) -> None:
        """Spawn *count* sparks around *center* using the injected *rng*."""
        self.particles: list[_Spark] = []
        for _ in range(count):
            angle = rng.uniform(0.0, math.tau)
            speed = rng.uniform(0.6, 2.2)
            self.particles.append(
                _Spark(
                    x=float(center[0]),
                    y=float(center[1]),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    age=0,
                    life=rng.randint(18, 34),
                    color=rng.choice(_SPARK_COLORS),
                )
            )

    @property
    def particle_count(self) -> int:
        """Number of live sparks."""
        return len(self.particles)

    @property
    def alive(self) -> bool:
        """True while any spark is still twinkling."""
        return bool(self.particles)

    def update(self, frames: int = 1) -> None:
        """Advance *frames* logic frames (pure logic, deterministic)."""
        for _ in range(frames):
            survivors: list[_Spark] = []
            for p in self.particles:
                p.x += p.vx
                p.y += p.vy
                p.vx *= 0.92
                p.vy = p.vy * 0.92 - 0.03  # sparks float up as they die
                p.age += 1
                if p.age < p.life:
                    survivors.append(p)
            self.particles = survivors

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        """Paint live sparks with per-pixel alpha; plus-shape twinkle."""
        w, h = surface.get_size()
        for p in self.particles:
            alpha = max(0, min(255, int(255 * (1.0 - p.age / p.life))))
            if alpha == 0:
                continue
            rgba = (*p.color, alpha)
            cx = int(round(p.x)) + offset[0]
            cy = int(round(p.y)) + offset[1]
            shape = _PLUS_OFFSETS if (p.age // 3) % 2 == 0 else ((0, 0),)
            for dx, dy in shape:
                px, py = cx + dx, cy + dy
                if 0 <= px < w and 0 <= py < h:
                    surface.set_at((px, py), rgba)


@dataclass
class _Puff:
    """One dust blob: position, drift, growing radius, age."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    growth: float
    age: int
    life: int


class DustPuff:
    """Soft translucent smoke puff that expands and fades (hard drop, D13)."""

    _COLOR: Color = PALETTE["CREAM"]
    _MAX_ALPHA = 110  # never opaque — it is smoke

    def __init__(
        self,
        center: tuple[int, int],
        rng: random.Random,
        count: int = 6,
    ) -> None:
        """Spawn *count* blobs along the landing row using the injected *rng*."""
        self.particles: list[_Puff] = []
        for _ in range(count):
            self.particles.append(
                _Puff(
                    x=center[0] + rng.uniform(-5.0, 5.0),
                    y=center[1] + rng.uniform(-1.0, 1.0),
                    vx=rng.uniform(-0.4, 0.4),
                    vy=rng.uniform(-0.35, -0.1),  # smoke rises
                    radius=rng.uniform(1.0, 2.0),
                    growth=rng.uniform(0.12, 0.3),
                    age=0,
                    life=rng.randint(18, 28),
                )
            )

    @property
    def particle_count(self) -> int:
        """Number of live blobs."""
        return len(self.particles)

    @property
    def alive(self) -> bool:
        """True while any blob is still visible."""
        return bool(self.particles)

    def update(self, frames: int = 1) -> None:
        """Advance *frames* logic frames (pure logic, deterministic)."""
        for _ in range(frames):
            survivors: list[_Puff] = []
            for p in self.particles:
                p.x += p.vx
                p.y += p.vy
                p.radius += p.growth
                p.age += 1
                if p.age < p.life:
                    survivors.append(p)
            self.particles = survivors

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        """Blit each blob as a translucent circle (per-pixel alpha)."""
        for p in self.particles:
            alpha = max(0, min(255, int(self._MAX_ALPHA * (1.0 - p.age / p.life))))
            if alpha == 0:
                continue
            r = max(1, int(round(p.radius)))
            stamp = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(stamp, (*self._COLOR, alpha), (r, r), r)
            surface.blit(
                stamp,
                (
                    int(round(p.x)) - r + offset[0],
                    int(round(p.y)) - r + offset[1],
                ),
            )
