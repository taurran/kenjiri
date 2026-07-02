# Kenjiri macOS Port — Handoff Brief

**For: Claude running on macOS.** This is a **platform addition, NOT a version-up** — v1.0.0 stays
v1.0.0. Do not change gameplay, assets, scoring, or any decision in `.planning/DECISIONS.md`. The
deliverable is `kenjiri.app` (+ optional `.dmg`) attached to the existing v1.0.0 GitHub release.

## What Kenjiri is (30 seconds)
Corgi-themed NES-style Tetris. Python 3.12 / pygame-ce / uv. 230-test pytest suite. Windows exe ships
via PyInstaller (`kenjiri.spec`). Everything is cross-platform EXCEPT the four items below.

## Setup on the Mac
```bash
git clone https://github.com/taurran/kenjiri && cd kenjiri
uv sync --all-groups          # installs pinned deps incl. pyinstaller (uv.lock is authoritative)
uv run pytest tests/ -q       # must be 230 passed BEFORE you change anything
uv run python -m kenjiri      # sanity: the game should open and play right now on macOS
```

## Change 1 — `src/kenjiri/persistence/paths.py` (the only src change)
`data_dir()` currently resolves `%LOCALAPPDATA%\Kenjiri` (Windows env var). Add a darwin branch so
macOS uses `~/Library/Application Support/Kenjiri`, keeping ALL existing guarantees: env-injectable
for tests, absolute-path + no-`..` validation, realpath prefix-containment, None (session-only
degraded mode) on any failure, never a CWD fallback. Pattern:

```python
if sys.platform == "darwin":
    base = Path.home() / "Library" / "Application Support"   # then same guards as the win path
else:
    ...existing LOCALAPPDATA logic unchanged...
```
Keep the injected `env` parameter meaningful on both platforms (tests must stay green on macOS —
the existing LOCALAPPDATA tests exercise the win branch via injected env dicts; add a small darwin
test in `tests/test_persistence.py` mirroring the None/degraded negatives). Log path (`applog.py`)
derives from `data_dir()` — verify, it should need no change.

## Change 2 — icon: add `.icns` output to `tools/make_icon.py`
It already renders deterministic PNGs (16/32/48/256) from `kenjiri.gfx.sprites.corgi_title()`.
Add a `--icns` mode emitting `assets/icon.icns` (use `iconutil` via an `icon.iconset/` dir on macOS,
or the `icnsutil` PyPI package if you prefer pure-python — if you add a dep, it goes in the `dev`
group via `uv add --dev`). Keep it deterministic (no timestamps). Do NOT touch `assets/manifest.json`.

## Change 3 — `kenjiri-mac.spec` (new file, sibling of `kenjiri.spec`)
Read `kenjiri.spec` first — copy its Analysis/datas exactly (bundles `assets/music` + `assets/sfx`;
entry `src/kenjiri/__main__.py`, `pathex=["src"]`). Differences for mac:
- Remove the Windows `VSVersionInfo` version-resource block (Windows-only).
- `EXE(..., console=False)` then wrap in:
```python
app = BUNDLE(exe, name="Kenjiri.app", icon="assets/icon.icns",
             bundle_identifier="ai.kataharness.kenjiri",
             info_plist={"CFBundleShortVersionString": "1.0.0",
                         "NSHighResolutionCapable": True})
```

## Build + verify (default-FAIL — all must pass)
```bash
uv run pytest tests/ -q                          # 230+ passed (incl. your new darwin tests)
uv run python tools/make_icon.py --icns          # assets/icon.icns exists, deterministic
uv run pyinstaller kenjiri-mac.spec --noconfirm  # dist/Kenjiri.app
./dist/Kenjiri.app/Contents/MacOS/kenjiri --smoke && echo SMOKE-OK   # must exit 0
open dist/Kenjiri.app                            # real launch: title screen + music, play a piece
# optional dmg:
hdiutil create -volname Kenjiri -srcfolder dist/Kenjiri.app -ov -format UDZO dist/kenjiri.dmg
```
Gatekeeper: unsigned app ⇒ right-click → Open on first launch (document in README; notarization is
out of scope, same posture as Windows SmartScreen).

## Ship
1. Commit: `feat(mac): platform support — darwin paths, icns, mac spec` (+ README: add a macOS row
   to the download section + Gatekeeper note). **No version bump anywhere.**
2. Push master. Attach artifacts to the EXISTING release:
   `gh release upload v1.0.0 dist/kenjiri.dmg` (or the zipped .app).

## Pointers (read before editing)
- `.planning/DECISIONS.md` — D15/D24/D28 govern paths/degraded modes; D26 packaging; ALL LOCKED.
- `src/kenjiri/persistence/paths.py` + `tests/test_persistence.py` — change 1 + its tests.
- `tools/make_icon.py` — change 2. `kenjiri.spec` — template for change 3.
- `README.md` download section — add macOS.
- Windows artifacts (`kenjiri.spec`, `assets/icon.ico`, the exe on the release) must be untouched.
