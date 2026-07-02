"""Kenjiri UI layer: app shell, fixed-timestep clock, scenes and HUD.

Everything display-owning lives here (D16/D23/D28) — the ``gfx`` modules
only build surfaces; this package is the sole caller of
``pygame.display.set_mode`` and the render loop.
"""
from __future__ import annotations
