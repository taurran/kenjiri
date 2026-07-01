"""Tests for the deterministic audio asset pipeline (T2 — D11, D12, D28).

Verifies, per the frozen plan:
- All 10 asset files are emitted and hashed into ``assets/manifest.json``.
- Regenerating to a temp dir reproduces the committed manifest hashes (D28).
- The committed asset files themselves match the manifest (tamper check).
- Durations fall inside the D11/D12 ranges (probed via stdlib ``wave``).
- Music tracks loop seamlessly: first/last 32 samples near zero.
- Regenerating twice yields byte-identical output (no timestamps, D28).

Music files are WAV (not OGG) per the audited orchestrator decision: the
pinned stack (numpy/stdlib/pygame-ce) has no OGG encoder, and WAV via the
stdlib ``wave`` module is the plan's sanctioned deterministic fallback.

No pygame required; no conftest.py needed (T3 owns it) — all path/env setup
happens inside this file.
"""
from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
ASSETS_DIR = REPO_ROOT / "assets"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import make_assets  # noqa: E402  (tools/ is not a package; path set above)

MUSIC_FILES = (
    "music/title.wav",
    "music/gameplay.wav",
    "music/gameover.wav",
)
SFX_FILES = (
    "sfx/lock.wav",
    "sfx/harddrop.wav",
    "sfx/clear.wav",
    "sfx/kenjiri.wav",
    "sfx/levelup.wav",
    "sfx/gameover.wav",
    "sfx/menu.wav",
)
ALL_FILES = MUSIC_FILES + SFX_FILES

# D11 music duration ranges (seconds), D12/plan SFX ranges.
MUSIC_DURATION_RANGES = {
    "music/title.wav": (30.0, 45.0),
    "music/gameplay.wav": (60.0, 90.0),
    "music/gameover.wav": (15.0, 20.0),
}
SFX_MIN_S = 0.1
SFX_MAX_S = 1.5
FANFARE_MAX_S = 2.5  # levelup bark fanfare is allowed up to 2.5 s

LOOP_SEAM_SAMPLES = 32
LOOP_SEAM_THRESHOLD = 256  # int16 amplitude; "near zero"


def _sha256(path: Path) -> str:
    """Return the sha256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wav_info(path: Path) -> tuple[int, int, int, int]:
    """Return (nframes, framerate, sampwidth, nchannels) of a WAV file."""
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes(), wf.getframerate(), wf.getsampwidth(), wf.getnchannels()


def _wav_duration_s(path: Path) -> float:
    """Return the duration of a WAV file in seconds via stdlib wave."""
    nframes, framerate, _, _ = _wav_info(path)
    return nframes / framerate


def _wav_samples_int16(path: Path) -> list[int]:
    """Return all samples of a mono 16-bit WAV as a list of ints."""
    import array

    with wave.open(str(path), "rb") as wf:
        assert wf.getsampwidth() == 2
        assert wf.getnchannels() == 1
        raw = wf.readframes(wf.getnframes())
    return list(array.array("h", raw))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    """Regenerate the full asset set once into a temp dir (D28 check input)."""
    out = tmp_path_factory.mktemp("assets_regen_a")
    manifest = make_assets.build(out)
    return out, manifest


def _committed_manifest() -> dict:
    manifest_path = ASSETS_DIR / "manifest.json"
    assert manifest_path.is_file(), "assets/manifest.json missing — run tools/make_assets.py"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def test_all_files_emitted(built: tuple[Path, dict]) -> None:
    """All 10 asset files exist and the manifest covers exactly those files."""
    out, manifest = built
    for rel in ALL_FILES:
        assert (out / rel).is_file(), f"missing emitted asset: {rel}"
    assert set(manifest["files"].keys()) == set(ALL_FILES)
    on_disk = {p.relative_to(out).as_posix() for p in out.rglob("*.wav")}
    assert on_disk == set(ALL_FILES)


def test_regenerated_hashes_match_committed_manifest(built: tuple[Path, dict]) -> None:
    """D28: regenerating assets reproduces the committed content hashes."""
    out, manifest = built
    committed = _committed_manifest()
    assert manifest["files"] == committed["files"], (
        "regenerated hashes differ from committed assets/manifest.json — "
        "synth/composition changed without regenerating committed assets"
    )
    for rel, expected in committed["files"].items():
        assert _sha256(out / rel) == expected, f"hash drift for regenerated {rel}"


def test_committed_asset_files_match_manifest() -> None:
    """The committed files in assets/ match their manifest hashes (tamper check)."""
    committed = _committed_manifest()
    for rel, expected in committed["files"].items():
        path = ASSETS_DIR / rel
        assert path.is_file(), f"committed asset missing: {rel}"
        assert _sha256(path) == expected, f"committed asset does not match manifest: {rel}"


def test_wav_format(built: tuple[Path, dict]) -> None:
    """All assets are mono 16-bit WAV at 22050 or 44100 Hz."""
    out, _ = built
    for rel in ALL_FILES:
        _, framerate, sampwidth, nchannels = _wav_info(out / rel)
        assert nchannels == 1, f"{rel}: expected mono"
        assert sampwidth == 2, f"{rel}: expected 16-bit"
        assert framerate in (22050, 44100), f"{rel}: unexpected sample rate {framerate}"


def test_music_durations(built: tuple[Path, dict]) -> None:
    """Music durations fall inside the D11 ranges."""
    out, _ = built
    for rel, (lo, hi) in MUSIC_DURATION_RANGES.items():
        dur = _wav_duration_s(out / rel)
        assert lo <= dur <= hi, f"{rel}: duration {dur:.2f}s outside [{lo}, {hi}]"


def test_sfx_durations(built: tuple[Path, dict]) -> None:
    """Every SFX is short: 0.1–1.5 s (levelup fanfare up to 2.5 s)."""
    out, _ = built
    for rel in SFX_FILES:
        dur = _wav_duration_s(out / rel)
        hi = FANFARE_MAX_S if rel == "sfx/levelup.wav" else SFX_MAX_S
        assert SFX_MIN_S <= dur <= hi, f"{rel}: duration {dur:.3f}s outside [{SFX_MIN_S}, {hi}]"


def test_music_loop_seam(built: tuple[Path, dict]) -> None:
    """Music loops seamlessly: first/last 32 samples near zero amplitude."""
    out, _ = built
    for rel in MUSIC_FILES:
        samples = _wav_samples_int16(out / rel)
        head = samples[:LOOP_SEAM_SAMPLES]
        tail = samples[-LOOP_SEAM_SAMPLES:]
        assert max(abs(s) for s in head) <= LOOP_SEAM_THRESHOLD, f"{rel}: loop-start click"
        assert max(abs(s) for s in tail) <= LOOP_SEAM_THRESHOLD, f"{rel}: loop-end click"


def test_double_regeneration_byte_identical(
    built: tuple[Path, dict], tmp_path: Path
) -> None:
    """D28 negative check: two regenerations are byte-identical (no timestamps)."""
    out_a, _ = built
    out_b = tmp_path / "assets_regen_b"
    make_assets.build(out_b)
    for rel in ALL_FILES + ("manifest.json",):
        a = (out_a / rel).read_bytes()
        b = (out_b / rel).read_bytes()
        assert a == b, f"nondeterministic output for {rel}"
