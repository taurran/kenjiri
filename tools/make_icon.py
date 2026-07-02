"""Render ``assets/icon.ico`` from the in-code corgi pixel art (T7).

Imports :func:`kenjiri.gfx.sprites.corgi_title` (the single source of truth
for the title corgi — no duplicated pixel data), scales it to each icon size
with ``pygame.transform.scale`` (nearest-neighbor, crisp pixels per D16),
saves each size to an intermediate PNG via ``pygame.image.save``, and
assembles the ``.ico`` container by hand with the stdlib ``struct`` module.
ICO entries carrying raw PNG payloads are valid on Windows Vista+.

Deterministic per D28's spirit: no timestamps are embedded anywhere, and the
script renders everything TWICE and hard-fails if the two passes differ —
so a nondeterministic encoder can never silently ship. The resulting
``assets/icon.ico`` sha256 is printed and recorded in README build notes
(``assets/manifest.json`` is T2-owned and NOT touched here).

Run from the repo root: ``uv run python tools/make_icon.py``
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import tempfile
from pathlib import Path

# Headless-safe: dummy SDL drivers unless the environment chose otherwise.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import pygame  # noqa: E402

from kenjiri.gfx.sprites import corgi_title  # noqa: E402

#: Icon sizes required by the plan (Windows shell small/medium/large + 256).
SIZES: tuple[int, ...] = (16, 32, 48, 256)

#: Output path — T7-owned per the frozen ownership table.
ICO_PATH: Path = _ROOT / "assets" / "icon.ico"


def render_pngs() -> list[tuple[int, bytes]]:
    """Render the corgi at every icon size and return ``(size, png_bytes)``.

    Each size is a nearest-neighbor ``pygame.transform.scale`` of the 48x48
    :func:`corgi_title` sprite, written to an intermediate PNG file with
    ``pygame.image.save`` and read back as bytes.
    """
    base = corgi_title()
    out: list[tuple[int, bytes]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for size in SIZES:
            scaled = pygame.transform.scale(base, (size, size))
            png_path = Path(tmp) / f"icon-{size}.png"
            pygame.image.save(scaled, str(png_path))
            out.append((size, png_path.read_bytes()))
    return out


def build_ico(pngs: list[tuple[int, bytes]]) -> bytes:
    """Assemble an ICO container embedding *pngs* as PNG-format entries.

    Layout: ICONDIR (6 bytes) + one 16-byte ICONDIRENTRY per image + the
    raw PNG payloads. A width/height byte of 0 means 256 per the format.
    """
    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries = b""
    payload = b""
    offset = 6 + 16 * len(pngs)
    for size, data in pngs:
        dim = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII",
            dim,        # width  (0 = 256)
            dim,        # height (0 = 256)
            0,          # palette color count (none — truecolor PNG)
            0,          # reserved
            1,          # color planes
            32,         # bits per pixel (RGBA)
            len(data),  # payload size
            offset,     # payload offset from file start
        )
        payload += data
        offset += len(data)
    return header + entries + payload


def main() -> int:
    """Render, self-check determinism, write the icon, print its sha256."""
    pygame.init()
    try:
        first = build_ico(render_pngs())
        second = build_ico(render_pngs())
    finally:
        pygame.quit()
    if first != second:
        print("FATAL: icon render is nondeterministic (two passes differ)")
        return 1
    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICO_PATH.write_bytes(first)
    digest = hashlib.sha256(first).hexdigest()
    print(f"wrote {ICO_PATH} ({len(first)} bytes, sizes {SIZES})")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
