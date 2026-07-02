# Kenjiri

> ## 🎮 Download & play — Windows & macOS
>
> **No install, no Python, nothing else.**
>
> **Windows x64:** [⬇ kenjiri.exe](https://github.com/taurran/kenjiri/releases/latest/download/kenjiri.exe) — just double-click and play.
> SmartScreen will warn on an unsigned exe — click *More info → Run anyway*. First launch takes ~2 s to unpack.
>
> **macOS (Apple Silicon):** [⬇ kenjiri.dmg](https://github.com/taurran/kenjiri/releases/latest/download/kenjiri.dmg) — open the disk image and drag **Kenjiri** to Applications.
> The app is unsigned, so on first launch **right-click → Open**, then confirm (same posture as Windows SmartScreen; notarization is out of scope).
>
> ([All releases](https://github.com/taurran/kenjiri/releases))

A corgi-themed, NES-style falling-block puzzle for Windows — built end-to-end
as a **KataHarness one-shot showcase** (frozen decision ledger, parallel
worker waves, adversarial gates): **spec → playable, tested, packaged game in
about an hour**, 230 tests, zero plan drift. Modern guideline mechanics
(7-bag, SRS kicks, hold, ghost, hard drop) with NES scoring and pacing, a
chibi pixel corgi mascot, and a fully synthesized 8-bit soundtrack. Clearing
four lines at once is a **Kenjiri**.

## Controls

| Key | Action |
| --- | --- |
| ← / → | Move left / right |
| ↓ | Soft drop |
| ↑ or X | Rotate clockwise |
| Z or Ctrl | Rotate counter-clockwise |
| Space | Hard drop |
| C or Shift | Hold |
| P or Esc | Pause |
| Q (while paused) | Quit to title (run abandoned, score not saved) |

Title screen: **Enter**, **Space**, or **click** to start; **Esc** quits the app.

## Scoring

NES table, multiplied by (level + 1):

| Clear | Base points |
| --- | --- |
| Single | 40 |
| Double | 100 |
| Triple | 300 |
| **Kenjiri** (4 lines) | **1200** |

Soft drop earns +1 per row while held; hard drop earns +2 per row dropped.
Level advances every 10 lines. Score is awarded at lock using the level
*before* any level-up from that clear.

## Build

Requires Python 3.12 via [uv](https://docs.astral.sh/uv/).

**Windows:**

```
uv sync --all-groups
uv run python tools/make_assets.py
uv run python tools/make_icon.py
uv run pyinstaller kenjiri.spec --noconfirm
```

Run the result: `dist/kenjiri.exe` (or dev-run with `uv run python -m kenjiri`;
`--smoke` performs a headless self-check and exits 0).

**macOS (Apple Silicon):**

```
uv sync --all-groups
uv run python tools/make_assets.py
uv run python tools/make_icon.py --icns
uv run pyinstaller kenjiri-mac.spec --noconfirm
```

Run the result: `dist/Kenjiri.app` (smoke-check with
`./dist/Kenjiri.app/Contents/MacOS/kenjiri --smoke`). Package for
distribution with
`hdiutil create -volname Kenjiri -srcfolder dist/Kenjiri.app -ov -format UDZO dist/kenjiri.dmg`.

### Build notes

- **Assets are canonical as committed.** `tools/make_assets.py` regenerates
  the audio deterministically (fixed seed, no timestamps) and the test suite
  verifies its output against the sha256 manifest in `assets/manifest.json`.
  Music tracks are WAV (`assets/music/*.wav`), as are all SFX
  (`assets/sfx/*.wav`). The PyInstaller spec bundles `assets/music` and
  `assets/sfx` as data files — the app never re-renders assets at runtime
  (`tools/make_assets.py` is never imported by the game).
- **Icon:** `tools/make_icon.py` renders `assets/icon.ico` (16/32/48/256 px,
  PNG-in-ICO container) from the in-code title-corgi pixel art via
  nearest-neighbor scaling. The script renders twice and fails if the passes
  differ, so the icon is deterministic.
  - `assets/icon.ico` sha256:
    `e6beb2e5333748cdcc8310ebbb14d65396f4cc79fd37aad6dd3e2dc014e94d89`
  - On macOS, `tools/make_icon.py --icns` emits `assets/icon.icns` from the
    same corgi art (hand-assembled PNG-payload ICNS container, likewise
    rendered twice and compared for determinism).
- **Exe metadata:** onefile, no console window, version 1.0.0, product name
  "Kenjiri" (defined inline in `kenjiri.spec`).
- **macOS app metadata:** `kenjiri-mac.spec` wraps the same onefile build in a
  `Kenjiri.app` bundle (`bundle_identifier` `ai.kataharness.kenjiri`,
  `CFBundleShortVersionString` 1.0.0, high-resolution capable). No Windows
  version resource is used on macOS.

## High scores & logs

- High score: `%LOCALAPPDATA%\Kenjiri\kenjiri.db` (Windows) /
  `~/Library/Application Support/Kenjiri/kenjiri.db` (macOS) — SQLite, single
  TOP record.
- Log file: `%LOCALAPPDATA%\Kenjiri\kenjiri.log` (Windows) /
  `~/Library/Application Support/Kenjiri/kenjiri.log` (macOS) — append;
  truncated above 1 MB.

If the data directory is unresolvable or the DB is locked/unwritable, the game
plays on without persistence (session-best TOP) — it never falls back to a
relative path and never crashes over storage.

## Security note: PyInstaller onefile extraction

`kenjiri.exe` is a PyInstaller **onefile** build: at launch it self-extracts
to a per-user temporary directory (`%TEMP%\_MEIxxxxxx`) and runs from there,
which adds a short first-launch delay. This extraction pattern has a historic
DLL-planting vulnerability class (cf. **CVE-2019-16784**, fixed in modern
PyInstaller). The risk is explicitly accepted for this single-user personal
game on Windows 11: `%TEMP%` is per-user, and PyInstaller is pinned current
(>= 6.21.0) via `uv.lock`.

## Tests

```
uv run pytest tests/ -q
```
