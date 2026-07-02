"""Compose and render every Kenjiri audio asset, deterministically (T2).

Renders three ORIGINAL chiptune tracks (D11) and seven corgi-themed SFX
(D12) with the NES-APU-style synthesizer in ``tools/synth.py``, then writes
``assets/manifest.json`` mapping every emitted file to its sha256 (D28).

Format note (orchestrator decision, audited on the board): music files are
WAV — ``assets/music/{title,gameplay,gameover}.wav`` — because the pinned
stack (numpy / stdlib / pygame-ce) has no OGG *encoder*. This is the frozen
plan's sanctioned fallback, not a deviation. Music is mono 22050 Hz 16-bit
to keep sizes moderate; SFX are mono 22050 Hz 16-bit.

Determinism (D28): fixed LFSR seed, no timestamps, stdlib ``wave`` output,
sorted-key JSON manifest — regenerating twice is byte-identical, and the
pytest suite (tests/test_assets.py) enforces it against the committed
hashes.

None of the three melodies quotes Korobeiniki (the Tetris theme) — D11
explicitly forbids it. Each track's note rows are documented in its
composer function's docstring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import synth  # noqa: E402  (tools/ is not a package)

SR = synth.SAMPLE_RATE

# Channel gains shared by the music mixer.
GAIN_LEAD = 0.26
GAIN_HARMONY = 0.13
GAIN_BASS = 0.30
GAIN_NOISE = 0.07


def _rows_total(rows: list[tuple[object, float]]) -> float:
    """Sum the row counts of a note-row list (composition length check)."""
    return sum(r for _, r in rows)


def _mix_music(
    lead: list[synth.NoteRow], lead_duty: float,
    harmony: list[synth.NoteRow], harmony_duty: float,
    bass: list[synth.NoteRow],
    perc: list[synth.NoiseRow],
    row_dur: float,
    expected_rows: float,
) -> np.ndarray:
    """Render a 4-channel APU arrangement to int16 with a seamless loop seam."""
    for name, ch in (("lead", lead), ("harmony", harmony), ("bass", bass), ("perc", perc)):
        got = _rows_total(ch)  # type: ignore[arg-type]
        if got != expected_rows:
            raise ValueError(f"{name} channel has {got} rows, expected {expected_rows}")
    ch_lead = synth.render_note_channel(
        lead, row_dur, SR, "pulse", duty=lead_duty, gain=GAIN_LEAD)
    ch_harm = synth.render_note_channel(
        harmony, row_dur, SR, "pulse", duty=harmony_duty, gain=GAIN_HARMONY)
    ch_bass = synth.render_note_channel(
        bass, row_dur, SR, "triangle", gain=GAIN_BASS,
        attack=0.005, decay=0.15, sustain=0.7, release=0.03)
    ch_perc = synth.render_noise_channel(perc, row_dur, SR, gain=GAIN_NOISE)
    track = synth.mix(ch_lead, ch_harm, ch_bass, ch_perc)
    return synth.to_int16(synth.loop_seam(track, SR))


def compose_title() -> np.ndarray:
    """Title theme — "Corgi Strut", 36.0 s loop (row = 0.25 s, 144 rows).

    D Lydian with chromatic color (F-natural, A#) and an angular, art-rock
    melodic contour; 16 bars of 7/8 followed by an 8-bar 4/4 coda that ends
    on a rest bar (the loop point). Not Korobeiniki, nor any fragment of it.

    Lead note rows (rows in parentheses):
      BAR_A (7/8): D4 F#4 G#4 C#5(2) B4 E4
      BAR_B (7/8): A4 G#4 F4 F#4(2) rest C#5        (chromatic F-natural)
      BAR_C (7/8): E5 D5 A#4 B4(2) F#4 D4           (tritone A# color)
      BAR_D (7/8): G#4 A4 B4 C#5 D5 E5 rest         (rising scalar burst)
      phrase = A B A C A B D C, played twice (112 rows)
      CODA (4/4): [D5(2) C#5 G#4] x4 · A4(2) E4 F#4 · F#4 E4 D4(2) ·
                  D4(3) rest · rest(4)
    Bass (triangle): D2/A2/G#2 vamp against B1/F#2/F2 answer, walking the
    same 7/8 grid; coda alternates D2–A2 and settles on D2.
    Harmony (25% pulse): off-beat D3/E3 vs C#3/F#3 stabs.
    Percussion (LFSR noise): hat pattern on rows 1,3,4,6,7 of each 7/8 bar.
    """
    bar_a = [("D4", 1), ("F#4", 1), ("G#4", 1), ("C#5", 2), ("B4", 1), ("E4", 1)]
    bar_b = [("A4", 1), ("G#4", 1), ("F4", 1), ("F#4", 2), (None, 1), ("C#5", 1)]
    bar_c = [("E5", 1), ("D5", 1), ("A#4", 1), ("B4", 2), ("F#4", 1), ("D4", 1)]
    bar_d = [("G#4", 1), ("A4", 1), ("B4", 1), ("C#5", 1), ("D5", 1), ("E5", 1), (None, 1)]
    phrase = bar_a + bar_b + bar_a + bar_c + bar_a + bar_b + bar_d + bar_c
    coda = (
        [("D5", 2), ("C#5", 1), ("G#4", 1)] * 4
        + [("A4", 2), ("E4", 1), ("F#4", 1)]
        + [("F#4", 1), ("E4", 1), ("D4", 2)]
        + [("D4", 3), (None, 1)]
        + [(None, 4)]
    )
    lead = phrase * 2 + coda

    hbar_1 = [(None, 1), ("D3", 1), (None, 1), ("E3", 2), (None, 2)]
    hbar_2 = [(None, 1), ("C#3", 1), (None, 1), ("F#3", 2), (None, 2)]
    harmony = (hbar_1 + hbar_2) * 8 + [("D3", 2), (None, 2)] * 6 + [("A2", 4)] + [(None, 4)]

    tbar_1 = [("D2", 2), ("D2", 1), ("A2", 2), ("G#2", 2)]
    tbar_2 = [("B1", 2), ("B1", 1), ("F#2", 2), ("F2", 2)]
    bass = (tbar_1 + tbar_2) * 8 + [("D2", 2), ("A2", 2)] * 6 + [("D2", 4)] + [(None, 4)]

    nbar = [(6000.0, 1), (None, 1), (3000.0, 1), (6000.0, 1), (None, 1), (6000.0, 1), (2500.0, 1)]
    perc = nbar * 16 + [(6000.0, 1), (None, 3)] * 7 + [(None, 4)]

    return _mix_music(lead, 0.50, harmony, 0.25, bass, perc,
                      row_dur=0.25, expected_rows=144)


def compose_gameplay() -> np.ndarray:
    """Gameplay theme — "Herding Blocks", 72.0 s loop (row = 0.20 s, 360 rows).

    E minor/dorian with heavy chromatic sidesteps (A#, D#, F-natural) and
    deliberately angular leaps; meter shifts between 5/4 (10-row bars) and
    7/8 (7-row bars): 16 bars of 5/4, 20 bars of 7/8, then 6 bars of 5/4
    with an outro bar ending in a rest (loop point). No Korobeiniki quote.

    Lead note rows:
      GA (5/4): E4 G4 A4 A#4 B4(2) D5 C#5 G4 rest    (chromatic rise)
      GB (5/4): E5 B4 F5 E5 D5(2) A4 A#4 B4(2)       (tritone F over B)
      GC (5/4): G4 F#4 F4 E4 B4(2) E4 D4 E4(2)       (chromatic descent)
      GD (5/4): C5 B4 A#4 B4 F#5(2) E5 D5 B4 rest    (angular 5th leap)
      GE (7/8): E4 F#4 G4 A#4 B4 D5 E5
      GF (7/8): D5 C#5 C5 B4(2) F#4 G4               (chromatic slide)
      GG (7/8): A4 B4 C5 E5 D#5 B4 rest
      GH (7/8): G4(2) F#4 E4(2) rest(2)
      GZ (5/4 outro): E4(2) B3(2) E4(4) rest(2)
      Section 1 = (GA GB GC GD) x4; Section 2 = (GE GF GG GH) x5;
      Section 3 = GA GC GB GC GA GZ.
    Bass (triangle): E2 pedal vamps with G2/A2/A#2 chromatic turns against
    B1/D2/C#2/C2 answers; 7/8 section walks E2–B2–D2 vs C2–G2–B1.
    Harmony (12.5% pulse): sparse off-beat arpeggio dots (E3 G3 B3 / D3 F#3 A3).
    Percussion: driving 5/4 and 7/8 hat/kick LFSR patterns.
    """
    ga = [("E4", 1), ("G4", 1), ("A4", 1), ("A#4", 1), ("B4", 2), ("D5", 1), ("C#5", 1), ("G4", 1), (None, 1)]
    gb = [("E5", 1), ("B4", 1), ("F5", 1), ("E5", 1), ("D5", 2), ("A4", 1), ("A#4", 1), ("B4", 2)]
    gc = [("G4", 1), ("F#4", 1), ("F4", 1), ("E4", 1), ("B4", 2), ("E4", 1), ("D4", 1), ("E4", 2)]
    gd = [("C5", 1), ("B4", 1), ("A#4", 1), ("B4", 1), ("F#5", 2), ("E5", 1), ("D5", 1), ("B4", 1), (None, 1)]
    ge = [("E4", 1), ("F#4", 1), ("G4", 1), ("A#4", 1), ("B4", 1), ("D5", 1), ("E5", 1)]
    gf = [("D5", 1), ("C#5", 1), ("C5", 1), ("B4", 2), ("F#4", 1), ("G4", 1)]
    gg = [("A4", 1), ("B4", 1), ("C5", 1), ("E5", 1), ("D#5", 1), ("B4", 1), (None, 1)]
    gh = [("G4", 2), ("F#4", 1), ("E4", 2), (None, 2)]
    gz = [("E4", 2), ("B3", 2), ("E4", 4), (None, 2)]
    lead = (ga + gb + gc + gd) * 4 + (ge + gf + gg + gh) * 5 + ga + gc + gb + gc + ga + gz

    hh1 = [(None, 1), ("E3", 1), (None, 2), ("G3", 1), (None, 2), ("B3", 1), (None, 2)]
    hh2 = [(None, 1), ("D3", 1), (None, 2), ("F#3", 1), (None, 2), ("A3", 1), (None, 2)]
    hh3 = [(None, 1), ("E3", 1), (None, 1), ("B3", 1), (None, 3)]
    harmony = (hh1 + hh2) * 8 + hh3 * 20 + (hh1 + hh2) * 3

    bb1 = [("E2", 2), ("E2", 1), ("E2", 2), ("G2", 2), ("A2", 2), ("A#2", 1)]
    bb2 = [("B1", 2), ("B1", 1), ("D2", 2), ("D2", 2), ("C#2", 2), ("C2", 1)]
    bb3 = [("E2", 2), ("B2", 1), ("E2", 2), ("D2", 2)]
    bb4 = [("C2", 2), ("G2", 1), ("C2", 2), ("B1", 2)]
    bass = (bb1 + bb2) * 8 + (bb3 + bb4) * 10 + (bb1 + bb2) * 3

    nn1 = [(2200.0, 1), (None, 1), (7000.0, 1), (None, 1), (2200.0, 1),
           (7000.0, 1), (None, 1), (7000.0, 1), (2200.0, 1), (None, 1)]
    nn2 = [(2200.0, 1), (7000.0, 1), (None, 1), (2200.0, 1), (None, 1), (7000.0, 1), (None, 1)]
    perc = nn1 * 16 + nn2 * 20 + nn1 * 6

    return _mix_music(lead, 0.25, harmony, 0.125, bass, perc,
                      row_dur=0.20, expected_rows=360)


def compose_gameover() -> np.ndarray:
    """Game-over theme — "Good Dog, Long Day", 18.0 s (row = 0.30 s, 60 rows).

    Bittersweet-resolving-warm (D11): G major colored by borrowed bVI/bIII
    (Eb, Bb) before settling home on G; slow 4/4 (15 bars of 4 rows), the
    last bar a rest (fade/loop point). No Korobeiniki quote.

    Lead note rows (bars of 4):
      B4(2) A4 G4 · E4(2) G4(2) · F#4(2) D4 E4 · D4(4) ·
      Eb4(2) F4 G4 · Bb4(2) A4(2) · G4(2) E4 F#4 · G4(4) ·
      B4 C5 D5(2) · C5(2) A4(2) · B4(2) G4 A4 · B4(4) ·
      A4(2) G4(2) · G4(3) rest · rest(4)
    Bass (triangle, whole-bar): G2 C2 D2 G2 · Eb2 Bb1 C2 G2 ·
      G2 C2 G2 D2 · G2 G2 rest
    Harmony (25% pulse): soft off-beat guide tones (D4 E4 A3 B3 G4 F4 …).
    Percussion: one soft low-rate brush at each bar head, silent last 3 bars.
    """
    lead = (
        [("B4", 2), ("A4", 1), ("G4", 1)]
        + [("E4", 2), ("G4", 2)]
        + [("F#4", 2), ("D4", 1), ("E4", 1)]
        + [("D4", 4)]
        + [("Eb4", 2), ("F4", 1), ("G4", 1)]
        + [("Bb4", 2), ("A4", 2)]
        + [("G4", 2), ("E4", 1), ("F#4", 1)]
        + [("G4", 4)]
        + [("B4", 1), ("C5", 1), ("D5", 2)]
        + [("C5", 2), ("A4", 2)]
        + [("B4", 2), ("G4", 1), ("A4", 1)]
        + [("B4", 4)]
        + [("A4", 2), ("G4", 2)]
        + [("G4", 3), (None, 1)]
        + [(None, 4)]
    )
    harmony = (
        [(None, 2), ("D4", 2)]
        + [(None, 2), ("E4", 2)]
        + [(None, 2), ("A3", 2)]
        + [("B3", 4)]
        + [(None, 2), ("G4", 2)]
        + [(None, 2), ("F4", 2)]
        + [(None, 2), ("E4", 2)]
        + [("D4", 4)]
        + [(None, 2), ("G4", 2)]
        + [(None, 2), ("E4", 2)]
        + [(None, 2), ("D4", 2)]
        + [("D4", 4)]
        + [(None, 2), ("C4", 2)]
        + [("B3", 4)]
        + [(None, 4)]
    )
    bass_notes = ["G2", "C2", "D2", "G2", "Eb2", "Bb1", "C2", "G2",
                  "G2", "C2", "G2", "D2", "G2", "G2", None]
    bass: list[synth.NoteRow] = [(n, 4) for n in bass_notes]
    perc = [(1500.0, 1), (None, 3)] * 12 + [(None, 4)] * 3

    return _mix_music(lead, 0.50, harmony, 0.25, bass, perc,
                      row_dur=0.30, expected_rows=60)


def _finish_sfx(x: np.ndarray) -> np.ndarray:
    """Clip, edge-fade and quantize a finished SFX buffer."""
    return synth.to_int16(synth.edge_fade(np.clip(x, -0.98, 0.98), SR))


def sfx_lock() -> np.ndarray:
    """Soft thud (piece lock, D12): short low triangle drop + faint noise."""
    dur = 0.13
    n = int(round(dur * SR))
    body = synth.sweep(120.0, 55.0, dur, SR, "triangle") * synth.adsr(
        n, SR, attack=0.002, decay=0.07, sustain=0.0, release=0.02)
    thump = synth.noise(n, SR, 900.0) * synth.adsr(
        n, SR, attack=0.001, decay=0.03, sustain=0.0, release=0.01)
    return _finish_sfx(0.7 * body + 0.18 * thump)


def sfx_harddrop() -> np.ndarray:
    """Heavier slam (hard drop, D12): deeper, longer thud with more noise."""
    dur = 0.24
    n = int(round(dur * SR))
    body = synth.sweep(95.0, 38.0, dur, SR, "triangle") * synth.adsr(
        n, SR, attack=0.002, decay=0.12, sustain=0.0, release=0.03)
    slam = synth.noise(n, SR, 520.0) * synth.adsr(
        n, SR, attack=0.001, decay=0.07, sustain=0.0, release=0.02)
    return _finish_sfx(0.75 * body + 0.30 * slam)


def sfx_clear() -> np.ndarray:
    """Pop (line clear, D12): quick rising square blip."""
    dur = 0.16
    n = int(round(dur * SR))
    pop = synth.sweep(480.0, 1150.0, dur, SR, "pulse", duty=0.5) * synth.adsr(
        n, SR, attack=0.002, decay=0.09, sustain=0.0, release=0.02)
    tick = synth.noise(n, SR, 6000.0) * synth.adsr(
        n, SR, attack=0.001, decay=0.015, sustain=0.0, release=0.005)
    return _finish_sfx(0.6 * pop + 0.12 * tick)


def sfx_kenjiri() -> np.ndarray:
    """Rising dog-whistle (Kenjiri 4-line clear, D12): two fast upward sweeps."""
    seg1_dur, gap_dur, seg2_dur = 0.20, 0.05, 0.30
    n1 = int(round(seg1_dur * SR))
    n2 = int(round(seg2_dur * SR))
    seg1 = synth.sweep(750.0, 2600.0, seg1_dur, SR, "triangle") * synth.adsr(
        n1, SR, attack=0.01, decay=0.25, sustain=0.8, release=0.02)
    seg2 = synth.sweep(900.0, 3300.0, seg2_dur, SR, "triangle") * synth.adsr(
        n2, SR, attack=0.01, decay=0.30, sustain=0.8, release=0.05)
    gap = np.zeros(int(round(gap_dur * SR)))
    return _finish_sfx(0.6 * np.concatenate([seg1, gap, seg2]))


def _bark(base_hz: float, dur: float = 0.09) -> np.ndarray:
    """One short pitched 'ruff': falling 25%-duty pulse + noise transient."""
    n = int(round(dur * SR))
    voiced = synth.sweep(base_hz * 1.7, base_hz * 0.85, dur, SR, "pulse", duty=0.25)
    voiced *= synth.adsr(n, SR, attack=0.003, decay=0.05, sustain=0.0, release=0.01)
    breath = synth.noise(n, SR, 3200.0) * synth.adsr(
        n, SR, attack=0.001, decay=0.03, sustain=0.0, release=0.005)
    return 0.75 * voiced + 0.3 * breath


def sfx_levelup() -> np.ndarray:
    """Excited bark fanfare (level up, D12): ascending barks then a C-major flourish.

    Four pitched barks rising 380→760 Hz, then a fast C5-E5-G5-C6 arpeggio
    capped with a held C6 — an EXCITED ascending figure, ≤ 2.5 s total.
    """
    total = 1.6
    out = np.zeros(int(round(total * SR)))

    def _place(seg: np.ndarray, at_s: float) -> None:
        s = int(round(at_s * SR))
        out[s:s + len(seg)] += seg

    for at, base in zip((0.0, 0.16, 0.34, 0.55), (380.0, 470.0, 600.0, 760.0)):
        _place(_bark(base), at)
    arp_note = 0.08
    for i, name in enumerate(("C5", "E5", "G5", "C6")):
        n = int(round(arp_note * SR))
        seg = synth.tone(synth.note_to_freq(name), n, SR, "pulse", duty=0.5)
        seg *= synth.adsr(n, SR, attack=0.003, decay=0.06, sustain=0.0, release=0.01)
        _place(0.5 * seg, 0.80 + i * arp_note)
    n_hold = int(round(0.40 * SR))
    hold = synth.tone(synth.note_to_freq("C6"), n_hold, SR, "pulse", duty=0.5)
    hold *= synth.adsr(n_hold, SR, attack=0.004, decay=0.30, sustain=0.0, release=0.05)
    _place(0.45 * hold, 1.12)
    return _finish_sfx(out)


def sfx_gameover() -> np.ndarray:
    """Sad puppy 'awwh' whine (top-out, D12): slow downward bend with vibrato."""
    dur = 1.3
    n = int(round(dur * SR))
    t = np.arange(n, dtype=np.float64) / SR
    u = (t / dur) ** 1.15
    freqs = 950.0 * (320.0 / 950.0) ** u
    freqs *= 1.0 + 0.03 * np.sin(2.0 * np.pi * 5.5 * t)
    whine = synth.tone_from_freq(freqs, SR, "triangle") * synth.adsr(
        n, SR, attack=0.06, decay=0.5, sustain=0.75, release=0.25)
    return _finish_sfx(0.7 * whine)


def sfx_menu() -> np.ndarray:
    """Menu blip (UI, D12): tiny two-step square chirp."""
    dur = 0.12
    n = int(round(dur * SR))
    freqs = np.full(n, 880.0)
    freqs[int(round(0.05 * SR)):] = 1320.0
    blip = synth.tone_from_freq(freqs, SR, "pulse", duty=0.25) * synth.adsr(
        n, SR, attack=0.002, decay=0.06, sustain=0.2, release=0.02)
    return _finish_sfx(0.5 * blip)


def build(out_dir: Path) -> dict[str, dict[str, str]]:
    """Render every asset into ``out_dir`` and write its manifest.json.

    Returns the manifest dict ``{"files": {relpath: sha256}}``. Fully
    deterministic (D28): same code ⇒ byte-identical files and manifest.
    """
    renderers: dict[str, np.ndarray] = {
        "music/title.wav": compose_title(),
        "music/gameplay.wav": compose_gameplay(),
        "music/gameover.wav": compose_gameover(),
        "sfx/lock.wav": sfx_lock(),
        "sfx/harddrop.wav": sfx_harddrop(),
        "sfx/clear.wav": sfx_clear(),
        "sfx/kenjiri.wav": sfx_kenjiri(),
        "sfx/levelup.wav": sfx_levelup(),
        "sfx/gameover.wav": sfx_gameover(),
        "sfx/menu.wav": sfx_menu(),
    }
    files: dict[str, str] = {}
    for rel, samples in renderers.items():
        path = out_dir / rel
        synth.write_wav(path, samples, SR)
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest: dict[str, dict[str, str]] = {"files": files}
    manifest_path = out_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True))
        fh.write("\n")
    return manifest


def main() -> int:
    """CLI entry point: render all assets (default: the repo's assets/ dir)."""
    parser = argparse.ArgumentParser(description="Render Kenjiri audio assets.")
    parser.add_argument(
        "--out", type=Path, default=_TOOLS_DIR.parent / "assets",
        help="output directory (default: <repo>/assets)")
    args = parser.parse_args()
    # CWE-23 guard: canonicalize the CLI-supplied output dir and refuse
    # traversal segments before any file is written under it.
    out_dir = args.out
    if any(part == ".." for part in out_dir.parts):
        parser.error("--out must not contain '..' path segments")
    out_dir = out_dir.resolve()
    manifest = build(out_dir)
    for rel, digest in sorted(manifest["files"].items()):
        print(f"{digest[:16]}  {rel}")
    print(f"wrote {len(manifest['files'])} assets + manifest.json -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
