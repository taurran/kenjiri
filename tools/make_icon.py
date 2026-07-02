"""Render ``assets/icon.ico`` (Windows) or ``assets/icon.icns`` (macOS) from
the in-code corgi pixel art (T7).

Imports :func:`kenjiri.gfx.sprites.corgi_title` (the single source of truth
for the title corgi — no duplicated pixel data), scales it to each icon size
with ``pygame.transform.scale`` (nearest-neighbor, crisp pixels per D16),
saves each size to an intermediate PNG via ``pygame.image.save``, and
assembles the container by hand with the stdlib ``struct`` module:

- **``.ico`` (default):** ICONDIR + ICONDIRENTRY headers + raw PNG payloads.
  ICO entries carrying raw PNG payloads are valid on Windows Vista+.
- **``.icns`` (``--icns``):** the ``icns`` magic + one ``OSType``/length/PNG
  entry per size. PNG-payload icns entries are read by macOS 10.7+/Finder.
  Hand-assembled (rather than shelling out to ``iconutil``) to match the
  ``.ico`` path's dependency-free, guaranteed-deterministic style — the macOS
  build spec (``kenjiri-mac.spec``) points ``BUNDLE`` at this file.

Deterministic per D28's spirit: no timestamps are embedded anywhere, and the
script renders everything TWICE and hard-fails if the two passes differ —
so a nondeterministic encoder can never silently ship. The resulting file's
sha256 is printed and recorded in README build notes (``assets/manifest.json``
is T2-owned and NOT touched here).

Run from the repo root:
    ``uv run python tools/make_icon.py``            # writes assets/icon.ico
    ``uv run python tools/make_icon.py --icns``     # writes assets/icon.icns
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

#: macOS icon output (sibling of ICO_PATH).
ICNS_PATH: Path = _ROOT / "assets" / "icon.icns"

#: ``.icns`` OSType -> pixel size. PNG-payload entries, read by macOS 10.7+.
#: 1x sizes plus the @2x retina variants Finder/Dock prefer.
ICNS_TYPES: tuple[tuple[bytes, int], ...] = (
    (b"icp4", 16),    # 16x16
    (b"icp5", 32),    # 32x32
    (b"ic07", 128),   # 128x128
    (b"ic08", 256),   # 256x256
    (b"ic09", 512),   # 512x512
    (b"ic10", 1024),  # 1024x1024 (512@2x)
    (b"ic11", 32),    # 16x16@2x
    (b"ic12", 64),    # 32x32@2x
    (b"ic13", 256),   # 128x128@2x
    (b"ic14", 512),   # 256x256@2x
)


def _render_png(base: pygame.Surface, size: int, tmp: str) -> bytes:
    """Nearest-neighbor scale *base* to ``size`` and return its PNG bytes."""
    scaled = pygame.transform.scale(base, (size, size))
    png_path = Path(tmp) / f"icon-{size}.png"
    pygame.image.save(scaled, str(png_path))
    return png_path.read_bytes()


def render_pngs() -> list[tuple[int, bytes]]:
    """Render the corgi at every ICO size and return ``(size, png_bytes)``.

    Each size is a nearest-neighbor ``pygame.transform.scale`` of the 48x48
    :func:`corgi_title` sprite, written to an intermediate PNG file with
    ``pygame.image.save`` and read back as bytes.
    """
    base = corgi_title()
    with tempfile.TemporaryDirectory() as tmp:
        return [(size, _render_png(base, size, tmp)) for size in SIZES]


def render_icns_entries() -> list[tuple[bytes, bytes]]:
    """Render the corgi for each ``.icns`` OSType, returning ``(ostype, png)``.

    Distinct pixel sizes are rendered once and reused across OSTypes that
    share a size (e.g. ``ic08`` and ``ic13`` are both 256x256).
    """
    base = corgi_title()
    cache: dict[int, bytes] = {}
    entries: list[tuple[bytes, bytes]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for ostype, size in ICNS_TYPES:
            if size not in cache:
                cache[size] = _render_png(base, size, tmp)
            entries.append((ostype, cache[size]))
    return entries


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


def build_icns(entries: list[tuple[bytes, bytes]]) -> bytes:
    """Assemble an ICNS container embedding *entries* as PNG-format icons.

    Layout: ``b"icns"`` magic + total file length (big-endian u32), then one
    entry per icon: 4-byte OSType + entry length (big-endian u32, inclusive
    of the 8-byte entry header) + the raw PNG payload.
    """
    body = b""
    for ostype, data in entries:
        assert len(ostype) == 4, f"OSType must be 4 bytes: {ostype!r}"
        body += ostype + struct.pack(">I", len(data) + 8) + data
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def main(argv: list[str] | None = None) -> int:
    """Render, self-check determinism, write the icon, print its sha256.

    With ``--icns`` writes ``assets/icon.icns``; otherwise writes the default
    ``assets/icon.ico``. Both are rendered twice and compared to guarantee a
    deterministic result (D28 spirit).
    """
    args = sys.argv[1:] if argv is None else argv
    want_icns = "--icns" in args

    pygame.init()
    try:
        if want_icns:
            first = build_icns(render_icns_entries())
            second = build_icns(render_icns_entries())
            out_path, kind = ICNS_PATH, "icns"
        else:
            first = build_ico(render_pngs())
            second = build_ico(render_pngs())
            out_path, kind = ICO_PATH, "ico"
    finally:
        pygame.quit()

    if first != second:
        print(f"FATAL: {kind} render is nondeterministic (two passes differ)")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(first)
    digest = hashlib.sha256(first).hexdigest()
    print(f"wrote {out_path} ({len(first)} bytes)")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
