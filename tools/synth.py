"""NES-APU-style deterministic chiptune synthesizer (T2 — D11, D12, D28).

Channel model (mirrors the NES APU):
- Two pulse channels: square waves with 12.5% / 25% / 50% duty cycles.
- Triangle channel: linear triangle wave (bass/melody).
- Noise channel: 15-bit linear-feedback shift register (feedback =
  bit0 XOR bit1, NES long mode), stepped at a selectable rate for
  "pitched" noise.

Determinism (D28): there is NO wall-clock, NO entropy source, and NO
timestamp anywhere in this module. The only pseudo-random element is the
LFSR, seeded with the fixed constant ``LFSR_SEED`` — rendering the same
composition twice produces byte-identical output. WAV files are written
with the stdlib ``wave`` module (mono, 16-bit), which embeds no metadata.

Sequencing model: a channel is a list of note rows ``(note, rows)`` where
``note`` is a pitch name like ``"F#4"`` (or a noise step rate in Hz for the
noise channel) and ``rows`` is the length in sequencer rows. ``None`` is a
rest. Row duration in seconds is supplied per track, so track length is an
exact, deterministic function of the note tables.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE: int = 22050
LFSR_SEED: int = 1  # fixed noise seed — the pipeline's only "RNG" (D28)
_LFSR_PERIOD_LEN: int = 32767  # full period of the 15-bit NES LFSR

NoteRow = tuple[str | None, float]
NoiseRow = tuple[float | None, float]

_NOTE_OFFSETS: dict[str, int] = {
    "C": 0, "C#": 1, "DB": 1,
    "D": 2, "D#": 3, "EB": 3,
    "E": 4,
    "F": 5, "F#": 6, "GB": 6,
    "G": 7, "G#": 8, "AB": 8,
    "A": 9, "A#": 10, "BB": 10,
    "B": 11,
}

_lfsr_cache: np.ndarray | None = None


def note_to_freq(name: str) -> float:
    """Convert a pitch name like ``"C4"``, ``"F#3"`` or ``"Bb2"`` to Hz (A4=440)."""
    letter = name[:-1].upper()
    octave = int(name[-1])
    if letter not in _NOTE_OFFSETS:
        raise ValueError(f"unknown note name: {name!r}")
    midi = (octave + 1) * 12 + _NOTE_OFFSETS[letter]
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _lfsr_period() -> np.ndarray:
    """Return one full ±1 period of the NES 15-bit LFSR (seed ``LFSR_SEED``)."""
    global _lfsr_cache
    if _lfsr_cache is None:
        reg = LFSR_SEED
        out = np.empty(_LFSR_PERIOD_LEN, dtype=np.float64)
        for i in range(_LFSR_PERIOD_LEN):
            out[i] = 1.0 if (reg & 1) else -1.0
            feedback = (reg ^ (reg >> 1)) & 1
            reg = (reg >> 1) | (feedback << 14)
        _lfsr_cache = out
    return _lfsr_cache


def pulse_from_phase(phase: np.ndarray, duty: float) -> np.ndarray:
    """Square wave (±1) at the given duty cycle from a phase array (in cycles)."""
    return np.where((phase % 1.0) < duty, 1.0, -1.0)


def triangle_from_phase(phase: np.ndarray) -> np.ndarray:
    """Triangle wave (±1) from a phase array (in cycles)."""
    return 4.0 * np.abs((phase % 1.0) - 0.5) - 1.0


def tone(freq_hz: float, n: int, sr: int, kind: str, duty: float = 0.5) -> np.ndarray:
    """Render ``n`` samples of a steady pulse or triangle tone (unenveloped)."""
    phase = np.arange(n, dtype=np.float64) * (freq_hz / sr)
    if kind == "pulse":
        return pulse_from_phase(phase, duty)
    if kind == "triangle":
        return triangle_from_phase(phase)
    raise ValueError(f"unknown tone kind: {kind!r}")


def tone_from_freq(
    freqs: np.ndarray, sr: int, kind: str, duty: float = 0.5
) -> np.ndarray:
    """Render a tone whose frequency varies per sample (phase-continuous)."""
    phase = np.cumsum(freqs) / sr
    if kind == "pulse":
        return pulse_from_phase(phase, duty)
    if kind == "triangle":
        return triangle_from_phase(phase)
    raise ValueError(f"unknown tone kind: {kind!r}")


def sweep(
    f0: float, f1: float, dur_s: float, sr: int, kind: str,
    duty: float = 0.5, curve: str = "exp", shape: float = 1.0,
) -> np.ndarray:
    """Render an unenveloped pitch sweep from ``f0`` to ``f1`` Hz over ``dur_s``.

    ``curve`` is ``"exp"`` (musical/log sweep) or ``"lin"``; ``shape`` bends
    the sweep-time mapping (t/dur)**shape for slower/faster onsets.
    """
    n = int(round(dur_s * sr))
    u = (np.arange(n, dtype=np.float64) / max(n, 1)) ** shape
    if curve == "exp":
        freqs = f0 * (f1 / f0) ** u
    elif curve == "lin":
        freqs = f0 + (f1 - f0) * u
    else:
        raise ValueError(f"unknown sweep curve: {curve!r}")
    return tone_from_freq(freqs, sr, kind, duty)


def noise(n: int, sr: int, rate_hz: float) -> np.ndarray:
    """Render ``n`` samples of LFSR noise stepped at ``rate_hz`` (±1, unenveloped)."""
    period = _lfsr_period()
    idx = np.floor(np.arange(n, dtype=np.float64) * (rate_hz / sr)).astype(np.int64)
    return period[idx % _LFSR_PERIOD_LEN]


def adsr(
    n: int, sr: int,
    attack: float = 0.004, decay: float = 0.10,
    sustain: float = 0.55, release: float = 0.02,
) -> np.ndarray:
    """Per-note attack/decay/sustain/release envelope, ``n`` samples long.

    Linear attack 0→1, exponential decay 1→sustain, then a linear release
    ramp to 0 over the final ``release`` seconds (click-free note ends).
    """
    env = np.full(n, sustain, dtype=np.float64)
    a = min(int(attack * sr), n)
    if a > 0:
        env[:a] = np.linspace(0.0, 1.0, a, endpoint=False)
    d_end = min(a + int(decay * sr), n)
    if d_end > a:
        k = np.linspace(0.0, 1.0, d_end - a, endpoint=False)
        env[a:d_end] = sustain + (1.0 - sustain) * np.exp(-4.0 * k)
    r = min(int(release * sr), n)
    if r > 0:
        env[n - r:] *= np.linspace(1.0, 0.0, r)
    return env


def render_note_channel(
    rows: list[NoteRow], row_dur: float, sr: int, kind: str,
    duty: float = 0.5, gain: float = 1.0,
    attack: float = 0.004, decay: float = 0.10,
    sustain: float = 0.55, release: float = 0.02,
) -> np.ndarray:
    """Render a pulse/triangle channel from note rows with per-note envelopes.

    Event boundaries are computed sample-accurately from the running row
    position so total length is exactly ``round(sum(rows) * row_dur * sr)``.
    """
    total_rows = sum(r for _, r in rows)
    n_total = int(round(total_rows * row_dur * sr))
    out = np.zeros(n_total, dtype=np.float64)
    pos = 0.0
    for note, nrows in rows:
        s = int(round(pos * row_dur * sr))
        e = int(round((pos + nrows) * row_dur * sr))
        if note is not None and e > s:
            seg = tone(note_to_freq(note), e - s, sr, kind, duty)
            seg *= adsr(e - s, sr, attack, decay, sustain, release)
            out[s:e] = seg * gain
        pos += nrows
    return out


def render_noise_channel(
    rows: list[NoiseRow], row_dur: float, sr: int,
    gain: float = 1.0, attack: float = 0.001,
    decay: float = 0.05, sustain: float = 0.0, release: float = 0.01,
) -> np.ndarray:
    """Render the noise channel; each row's "note" is an LFSR step rate in Hz."""
    total_rows = sum(r for _, r in rows)
    n_total = int(round(total_rows * row_dur * sr))
    out = np.zeros(n_total, dtype=np.float64)
    pos = 0.0
    for rate, nrows in rows:
        s = int(round(pos * row_dur * sr))
        e = int(round((pos + nrows) * row_dur * sr))
        if rate is not None and e > s:
            seg = noise(e - s, sr, rate)
            seg *= adsr(e - s, sr, attack, decay, sustain, release)
            out[s:e] = seg * gain
        pos += nrows
    return out


def mix(*channels: np.ndarray) -> np.ndarray:
    """Sum equal-length channels into one float track (clipped to ±0.98)."""
    n = len(channels[0])
    for ch in channels:
        if len(ch) != n:
            raise ValueError(f"channel length mismatch: {len(ch)} != {n}")
    return np.clip(np.sum(channels, axis=0), -0.98, 0.98)


def loop_seam(x: np.ndarray, sr: int, guard: int = 48, fade_s: float = 0.012) -> np.ndarray:
    """Shape a track's edges for a seamless loop (D11).

    Zeroes a small guard region at both ends (so the first/last samples are
    exactly at the loop point's silence) and applies a short linear fade
    inward from each guard — inaudible (~12 ms) but click-proof.
    """
    env = np.ones(len(x), dtype=np.float64)
    fn = int(fade_s * sr)
    env[:guard] = 0.0
    env[guard:guard + fn] = np.linspace(0.0, 1.0, fn, endpoint=False)
    env[-guard:] = 0.0
    env[-(guard + fn):-guard] = np.linspace(1.0, 0.0, fn)
    return x * env


def edge_fade(x: np.ndarray, sr: int, fade_s: float = 0.002) -> np.ndarray:
    """Apply a short linear fade-in/out at both ends (click-free SFX edges)."""
    fn = min(int(fade_s * sr), len(x) // 2)
    if fn > 0:
        x = x.copy()
        x[:fn] *= np.linspace(0.0, 1.0, fn, endpoint=False)
        x[-fn:] *= np.linspace(1.0, 0.0, fn)
    return x


def to_int16(x: np.ndarray) -> np.ndarray:
    """Convert a ±1 float track to little-endian 16-bit PCM samples."""
    return (np.clip(x, -1.0, 1.0) * 32767.0).round().astype("<i2")


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    """Write mono 16-bit PCM via the stdlib ``wave`` module (no metadata, D28)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
