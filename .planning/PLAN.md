---
plan: kenjiri-v1
status: frozen
baseline: 9597b3d
ownership:
  T1: [src/kenjiri/game/__init__.py, src/kenjiri/game/pieces.py, src/kenjiri/game/bag.py, tests/test_pieces.py, tests/test_bag.py]
  T2: [tools/synth.py, tools/make_assets.py, assets/music/title.ogg, assets/music/gameplay.ogg, assets/music/gameover.ogg, assets/sfx/lock.wav, assets/sfx/harddrop.wav, assets/sfx/clear.wav, assets/sfx/kenjiri.wav, assets/sfx/levelup.wav, assets/sfx/gameover.wav, assets/sfx/menu.wav, assets/manifest.json, tests/test_assets.py]
  T3: [src/kenjiri/gfx/__init__.py, src/kenjiri/gfx/palette.py, src/kenjiri/gfx/sprites.py, src/kenjiri/gfx/font.py, src/kenjiri/gfx/particles.py, tests/conftest.py, tests/test_gfx.py]
  T4: [src/kenjiri/persistence/__init__.py, src/kenjiri/persistence/paths.py, src/kenjiri/persistence/applog.py, src/kenjiri/persistence/highscore.py, tests/test_persistence.py]
  T5: [src/kenjiri/game/board.py, src/kenjiri/game/gravity.py, src/kenjiri/game/scoring.py, src/kenjiri/game/state.py, src/kenjiri/game/inputmap.py, tests/test_board.py, tests/test_scoring.py, tests/test_gravity.py, tests/test_state.py]
  T6: [src/kenjiri/__init__.py, src/kenjiri/__main__.py, src/kenjiri/ui/__init__.py, src/kenjiri/ui/timing.py, src/kenjiri/ui/app.py, src/kenjiri/ui/scenes.py, src/kenjiri/ui/hud.py, src/kenjiri/audio/__init__.py, src/kenjiri/audio/engine.py, tests/test_timing.py]
  T7: [kenjiri.spec, tools/make_icon.py, assets/icon.ico, README.md]
waves:
  wave1: [T1, T2, T3, T4]
  wave2: [T5]
  wave3: [T6]
  wave4: [T7]
depends_on:
  T5: [T1]
  T6: [T1, T2, T3, T4, T5]
  T7: [T6]
---

# Kenjiri — frozen PLAN (advanced tier)

The contract kata-orchestrate enforces. Adds NO new decisions — it sequences the frozen ledger
(`.planning/DECISIONS.md` D1–D28, all LOCKED, double convergence SHIP). Every worker: execute via
kata-tdd (vertical red→green), stay in your owned files, escalate — never improvise.

## Global conventions (binding on every task)

- Python 3.12, type hints on all functions, docstrings on all public functions/classes (operator standard).
- **Matrix coordinates (D25):** columns 1–10 left→right, rows 1–22 bottom-up. Rows 1–20 visible; rows 21–22
  are the hidden Buffer. A cell is `(col, row)`. All game-logic modules use this convention exclusively.
- **Frames** mean 60 fps reference logic frames (D5/D6/D23).
- Pure game logic (T1/T5) imports **no pygame** — testable headless. pygame-touching tests rely on
  `tests/conftest.py` setting `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy` before pygame import.
- Verify commands run from the repo root of the task's worktree; all are default-FAIL.

## Interface contracts (pinned so parallel workers cannot drift)

- `kenjiri.game.pieces`: `PieceKind = Literal["I","O","T","S","Z","J","L"]`.
  `CELLS: dict[PieceKind, tuple[frozenset[tuple[int,int]], ...]]` — 4 rotation states (index 0 = spawn), cells
  as offsets from a piece origin. `spawn_origin(kind) -> tuple[int,int]` placing spawn cells per D27 verbatim:
  "I spawns in row 21 (its single row); O occupies columns 5–6, rows 21–22; all other pieces occupy columns
  4–6, rows 21–22 (flat-side down)". `rotated(kind, state, direction) -> int` next state index.
  `KICKS: dict[...]` — SRS wall-kick offset tables: JLSTZ table + I table (standard SRS; O never kicks).
- `kenjiri.game.bag`: `class SevenBag: def __init__(self, rng: random.Random) -> None; def next(self) -> PieceKind;
  def peek(self, n: int = 1) -> list[PieceKind]` — 7-bag per D3: every 7 draws contain each kind exactly once.
- `kenjiri.game.board`: `class Board` over a `dict[tuple[int,int], PieceKind]`; `collides(cells) -> bool`
  (occupied or out of bounds cols 1–10 / rows 1–22); `lock(cells, kind) -> None`; `full_rows() -> list[int]`;
  `clear_rows(rows) -> None` (collapse down); `cell(col,row) -> PieceKind | None`.
- `kenjiri.game.state`: `class Game` — the authoritative state machine. Constructor
  `Game(rng: random.Random)`. `def step(self, inputs: InputFrame) -> list[GameEvent]` advances exactly ONE
  logic frame. `InputFrame` (from `inputmap`) carries pressed/held flags: left, right, soft_drop, rotate_cw,
  rotate_ccw, hard_drop, hold. `GameEvent = Enum(LOCK, HARD_DROP, CLEAR_SINGLE, CLEAR_DOUBLE, CLEAR_TRIPLE,
  CLEAR_KENJIRI, LEVEL_UP, TOP_OUT, HOLD_USED, SPAWN)` — the UI/audio layer consumes events; game logic never
  imports UI/audio. Exposed read-only properties: `board`, `active` (kind, cells, ghost_cells or None per D25),
  `hold_kind`, `hold_available`, `next_kind`, `score`, `lines`, `level`, `piece_counts: dict[PieceKind,int]`,
  `over: bool`, `clearing: list[int] | None` (rows mid-animation).
- `kenjiri.persistence.highscore`: `class HighScoreStore: def __init__(self, db_path: Path | None) -> None`
  (None ⇒ session-only degraded mode); `def top(self) -> int`; `def submit(self, score: int, lines: int,
  level: int) -> bool` (True = new record persisted).
- `kenjiri.gfx.sprites`: builders returning `pygame.Surface` — `block(kind) -> Surface` (8×8),
  `logo() -> Surface`, `corgi_title() -> Surface`, `mascot(state: MascotState, frame: int) -> Surface`
  (`MascotState = Enum(IDLE, HAPPY, HYPE, SAD)`), `piece_glyph(kind) -> Surface`.
  `kenjiri.gfx.font`: `render(text: str, color) -> Surface` 5×7 pixel font, digits+A–Z+basic punctuation.
  `kenjiri.gfx.palette`: `PALETTE: dict[str, tuple[int,int,int]]` — pastel piece colors per D10 + UI colors.
- `kenjiri.audio.engine`: `class Audio: def play(self, event: GameEvent | UiSound) -> None;
  def music(self, track: str) -> None` (track ∈ title|gameplay|gameover); ducking per D26.
- `kenjiri.ui.timing`: `class FrameClock` — pure (no pygame): `def owed(self, elapsed_s: float) -> int`
  implementing D28 verbatim: "clamped to a maximum catch-up of 3 logic frames (50 ms) per render frame; any
  measured frame gap > 250 ms discards the excess time and auto-pauses" — returns owed frame count and exposes
  `auto_pause_triggered: bool`.
- Asset filenames (binding): `assets/music/{title,gameplay,gameover}.ogg`,
  `assets/sfx/{lock,harddrop,clear,kenjiri,levelup,gameover,menu}.wav`, `assets/manifest.json`
  (sha256 per generated file), `assets/icon.ico`.

## STRIDE threat register (advanced tier)

| Surface | Task | Threats that apply | Mitigation (in-task) |
|---|---|---|---|
| SQLite DB + log under `%LOCALAPPDATA%\Kenjiri` | T4 | **T**ampering (user-writable file), **I**nfo disclosure (path), **D**oS (locked/corrupt DB) | Parameterized queries only; pathlib-built fixed path, never CWD/user input (D24/D28); corrupt/locked/unresolvable ⇒ recreate or session-only mode, never crash (D15/D24/D28); no PII stored — scores only. Tamper-with-own-savefile explicitly accepted (D24). |
| Asset generation pipeline | T2 | **T**ampering (asset drift vs source), **R**epudiation (unreproducible artifacts) | Deterministic synth (fixed seed, no timestamps — D28); `assets/manifest.json` sha256 + pytest hash-verification (D28); no network, no exec, numpy/stdlib only. |
| PyInstaller onefile exe | T7 | **E**oP/**T** (CVE-2019-16784 class: %TEMP% \_MEI extraction) | Accepted + recorded per D28 (per-user %TEMP%, single-user box, PyInstaller 6.21.0 pinned via uv.lock); `--noconsole` (D26); Snyk code+SCA clean gate (D17/D28). |
| Input handling / window events | T6 | **D**oS (event-loop stall, resize spam) | D28 FrameClock clamp + auto-pause; no dynamic code paths from input; keys map to a fixed enum (D4). |

Spoofing/EoP beyond the above: no auth, no network, no privilege boundary — N/A by construction (D24).

---

## T1 — rules-pieces (wave 1)

- **owns:** `src/kenjiri/game/__init__.py`, `src/kenjiri/game/pieces.py`, `src/kenjiri/game/bag.py`,
  `tests/test_pieces.py`, `tests/test_bag.py`
- **read_first:** DECISIONS D3, D25, D27; CONTEXT.md (Piece, Bag, Buffer); the Interface contracts above.
- **action:** Implement piece data + rotation + bag exactly per contract. All 7 pieces, 4 rotation states,
  standard SRS kick tables (JLSTZ + I; O has a single state, never kicks). Spawn per D27 verbatim (quoted in
  the contract). `SevenBag` per D3: "7-bag randomizer" — each bag of 7 contains every piece exactly once,
  order shuffled by the injected `random.Random`. `peek` must not consume. NEW capability — no analogs exist
  (greenfield). No pygame imports.
- **verify:** `uv run pytest tests/test_pieces.py tests/test_bag.py -q`
- **acceptance_criteria:**
  - Every piece/rotation state has exactly 4 cells; I spawn cells = {(4,21),(5,21),(6,21),(7,21)};
    O spawn cells = {(5,21),(6,21),(5,22),(6,22)} (columns 5–6, rows 21–22 per D27);
    T spawn flat-side down within columns 4–6, rows 21–22.
  - SRS: T at a wall kicks per the JLSTZ table (test at least one wall-kick and one floor-kick case);
    I uses the I-table (test one).
  - 1000 draws from `SevenBag(random.Random(42))`: every consecutive 7-window aligned to bag boundaries
    contains all 7 kinds; distribution exact per bag.
  - **Negative:** no piece ever has cells outside columns 1–10 / rows 1–22 after any legal spawn or kick;
    `peek` twice in a row returns identical sequences (no consumption).
- **risk:** wrong kick tables silently corrupt every downstream rotation feel; blast radius = T5/T6 gameplay.

## T2 — audio-pipeline (wave 1)

- **owns:** `tools/synth.py`, `tools/make_assets.py`, `assets/music/*.ogg` (3), `assets/sfx/*.wav` (7),
  `assets/manifest.json`, `tests/test_assets.py`
- **read_first:** DECISIONS D11, D12, D26, D28 (asset canonicality + determinism); asset filenames contract.
- **action:** `tools/synth.py`: NES-APU-style synthesizer (numpy) — 2 pulse channels (12.5/25/50% duty),
  triangle channel, noise channel (LFSR), per-note envelopes, 44.1 kHz 16-bit. `tools/make_assets.py`:
  compose + render the three tracks per D11 — title loop 30–45 s, gameplay loop 60–90 s, game-over 15–20 s
  "bittersweet-resolving-warm"; melodies ORIGINAL and deliberately angular/odd (shifting meter welcome);
  MUST NOT quote Korobeiniki (D11: "Korobeiniki explicitly avoided"). Render the 7 SFX per D12 verbatim: "soft
  thud (lock), heavier slam (hard drop), pop (line clear), rising dog-whistle (Kenjiri), excited bark fanfare
  (level up), sad puppy 'awwh' whine (top-out), menu blip (UI)". Determinism per D28: fixed RNG seed, no
  timestamps; write `assets/manifest.json` with sha256 of every emitted file. OGG for music (pygame-supported;
  if the pinned stack cannot encode OGG deterministically, WAV for music is the permitted fallback — update
  filenames contract via escalation, do NOT improvise silently). SFX = WAV. Music loops seamlessly (D11).
- **verify:** `uv run python tools/make_assets.py && uv run pytest tests/test_assets.py -q`
- **acceptance_criteria:**
  - All 10 asset files exist, durations within the D11 ranges (probe via decode), music tracks loop without a
    click (first/last samples near zero-crossing).
  - `tests/test_assets.py` regenerates to a temp dir and asserts sha256 equality with `assets/manifest.json`
    (D28 hash-verification).
  - **Negative:** regenerating twice yields byte-identical outputs (no timestamp/nondeterminism); no melodic
    line reproduces the Korobeiniki incipit (document the three melodies' note rows in module docstrings).
- **risk:** non-deterministic encoder output breaks the D28 hash gate late at integration; blast radius = T6/T7.

## T3 — gfx-sprites (wave 1)

- **owns:** `src/kenjiri/gfx/__init__.py`, `palette.py`, `sprites.py`, `font.py`, `particles.py`,
  `tests/conftest.py`, `tests/test_gfx.py`
- **read_first:** DECISIONS D8–D10, D13, D14, D19, D23 (mascot placement); sprite/palette/font contracts.
- **action:** `palette.py` per D10 verbatim: "I soft-aqua, L peach, J periwinkle, S mint, Z blush-rose,
  O butter-yellow, T lavender; cream/warm-orange/pink/mint UI framing". `sprites.py`: 8×8 block tile per kind
  (bevel/highlight NES style); KENJIRI striped logo (D9); title-screen chibi corgi (orange/cream, collar,
  tongue out — D9); mascot sprite ≈24×24, 4 emote states with 2 animation frames each (D14: idle tail-wag,
  happy, hype ears-up, sad droopy); per-piece HUD glyphs (D8). All pixel data as palette-indexed arrays in
  code — no external image files. `font.py`: 5×7 pixel font (digits, A–Z, ! . - ×). `particles.py` per D13:
  sparkle/star burst (line clear) + transparent dust puff (hard drop) as per-pixel-alpha surface emitters with
  pure `update(frames)` logic. `tests/conftest.py`: set dummy SDL drivers + `pygame.init()` fixture.
- **verify:** `uv run pytest tests/test_gfx.py -q`
- **acceptance_criteria:**
  - Every `PieceKind` has a block tile and glyph; all mascot state/frame combos render; logo and corgi render
    non-empty at expected sizes; font renders "KENJIRI 1200 PAWSED" without KeyError.
  - Particle emitters produce surfaces with per-pixel alpha and decay to zero particles within a bounded frame
    count.
  - **Negative:** no sprite builder touches the display (works with `SDL_VIDEODRIVER=dummy`, no
    `set_mode` calls in gfx modules); no color outside `PALETTE` is used by sprites (assert via palette scan).
- **risk:** display-coupled sprite code breaks headless tests and worktree merges; blast radius = T6.

## T4 — persistence (wave 1)

- **owns:** `src/kenjiri/persistence/__init__.py`, `paths.py`, `applog.py`, `highscore.py`,
  `tests/test_persistence.py`
- **read_first:** DECISIONS D15, D21, D24, D28; HighScoreStore contract; STRIDE row 1.
- **action:** `paths.py`: resolve `%LOCALAPPDATA%\Kenjiri` via `os.environ` + pathlib ONLY (D24); unresolvable
  ⇒ return None per D28 verbatim: "treated exactly as DB-unwritable: play without persistence, session-best
  TOP, log once. Never fall back to a relative/CWD path." `applog.py` per D28: file logger at
  `%LOCALAPPDATA%\Kenjiri\kenjiri.log`, truncate above 1 MB, silent-disable when unavailable. `highscore.py`
  per D15/D21: sqlite3 stdlib, schema `highscore(id=1, score, lines, level, achieved_at)`, schema-versioned;
  parameterized queries ONLY; absent/corrupt ⇒ recreate fresh, log, don't crash (D15); locked/unwritable ⇒
  session-only mode (D24); single transaction at submit (D24: "no partial DB writes").
- **verify:** `uv run pytest tests/test_persistence.py -q`
- **acceptance_criteria:**
  - Round-trip: submit(higher) persists + returns True; submit(lower) returns False and does not overwrite;
    reopening the store reads the persisted TOP (use tmp_path, never the real %LOCALAPPDATA%).
  - Corrupt DB file ⇒ store recreates and functions; `db_path=None` ⇒ session-only store works.
  - **Negative:** no SQL string interpolation anywhere (`grep` assert: no f-string/%-format containing SELECT/
    INSERT/UPDATE builds a query); tests never write outside tmp_path; a mid-submit exception leaves the prior
    record intact (transaction atomicity).
- **risk:** silent CWD fallback writes files where the exe runs; blast radius = user trust + D24 violation.

## T5 — rules-engine (wave 2, after T1)

- **owns:** `src/kenjiri/game/board.py`, `gravity.py`, `scoring.py`, `state.py`, `inputmap.py`,
  `tests/test_board.py`, `tests/test_scoring.py`, `tests/test_gravity.py`, `tests/test_state.py`
- **read_first:** DECISIONS D3–D7, D18, D21, D23, D25–D27; T1's shipped `pieces.py`/`bag.py`; Board/Game
  contracts above.
- **action:** Full rules state machine, pure logic, event-emitting (contract above). Board per contract.
  `gravity.py` per D6 verbatim: "framesPerRow(level) = max(48 − 3·level, 4)". `scoring.py` per D7 verbatim:
  "Single 40 · Double 100 · Triple 300 · Kenjiri (4 lines) 1200, each × (level + 1). Soft drop +1/row while
  held; hard drop +2/row dropped" and D7 edge: "Score awarded at lock using level before any level-up from
  that clear"; level per D6: advance every 10 lines; display caps per D7/D26 (score 9,999,999; internal lines
  unbounded, D26). `state.py`: spawn per D25/D27 incl. "on the spawn frame, if the cell below is free, the
  piece immediately falls one row" and block-out checked "at the spawn position before this drop" (D27);
  gravity accumulator; soft drop 20× gravity capped 1 row/frame (D5); DAS 10 frames / ARR 2 frames with D5
  edges ("Direction change mid-DAS resets the charge; DAS charge held through hard drop into next piece
  spawn") + D27 ("charge continues accruing during the line-clear animation, capped at full charge"); lock
  delay per D18 verbatim: "0.5 s lock delay; any successful move/rotate while grounded resets it, max 15
  resets per piece, then force-lock on next ground contact. Hard drop locks instantly" + "Reset counter clears
  when the piece falls to a new lowest row"; hold per D3/D19 (once per piece, re-enabled at next lock); ghost
  per D25 (suppressed while active piece entirely in Buffer); clear animation ~0.3 s = 18 frames, input events
  ignored during it except pause handled upstream (D4/D23/D27); no ARE on non-clearing locks (D26); top-out =
  block-out OR lock-out per D25 verbatim; `piece_counts` increments once at spawn incl. held-swapped (D8);
  TOP live-update is UI-side — Game only exposes score. Events per contract enum.
- **verify:** `uv run pytest tests/test_board.py tests/test_scoring.py tests/test_gravity.py tests/test_state.py -q`
- **acceptance_criteria:**
  - Gravity table spot checks: L0=48, L8=24, L14=6, L15+=4 (per D6 formula — note this is the LINEAR ramp, not
    the NES cliff).
  - Scoring: Kenjiri at level 2 = 3600; a double that lifts lines 9→11 scores at the pre-clear level; soft/hard
    drop points accrue per row.
  - Lock delay: grounded move resets ≤15 times then force-locks; hard drop locks instantly; falling to a new
    lowest row restores resets.
  - Full game simulation: seeded RNG, scripted inputs reach a Kenjiri clear emitting CLEAR_KENJIRI; blocked
    spawn emits TOP_OUT (block-out); a piece locked fully above row 20 emits TOP_OUT (lock-out).
  - **Negative:** no logic frame ever moves a piece into a colliding cell; hold twice within one piece is
    rejected (second is a no-op); no pygame import anywhere in `game/`; clearing rows in the Buffer does not
    crash and scores normally (D25).
- **risk:** state-machine timing bugs (DAS/lock-delay interactions) — the core feel; blast radius = the game.

## T6 — app-integration (wave 3, after T1–T5)

- **owns:** `src/kenjiri/__init__.py`, `src/kenjiri/__main__.py`, `src/kenjiri/ui/__init__.py`, `timing.py`,
  `app.py`, `scenes.py`, `hud.py`, `src/kenjiri/audio/__init__.py`, `audio/engine.py`, `tests/test_timing.py`
- **read_first:** DECISIONS D4, D8, D9, D11–D14, D16, D19–D21, D23, D26, D28; ALL shipped wave-1/2 modules;
  FrameClock/Audio contracts.
- **action:** `timing.py`: FrameClock per contract (pure; D28 numbers verbatim). `app.py`: pygame init
  (mixer failure ⇒ silent mode per D24), 256×240 canvas, resizable window default 3× (768×720), largest-
  integer-scale letterbox, nearest-neighbor only (D16); fixed-timestep loop driven by FrameClock; auto-pause
  on focus loss/minimize, gameplay scene only (D28). `scenes.py`: title per D9/D20 (logo, corgi, PUSH START —
  Enter/click/Space start at level 0; Esc exits per D26); gameplay scene wiring Game + HUD + particles +
  mascot; pause per D23/D26 ("PAWSED" panel, field dimmed 60%, music −50%, "P/ESC RESUME · Q QUIT TO TITLE",
  Q abandons unpersisted per D26, DAS cleared on resume per D4); game-over per D23 (SCORE/LINES/LEVEL, TOP +
  "NEW TOP!" when beaten, persist at top-out per D21, sad emote, whine SFX then game-over theme once, Enter →
  title). `hud.py` per D8/D19: STATISTICS left (7 glyphs + counters, cap 999), LINES top-center (4-digit
  reflow, clamp 9999 per D26), right column NEXT (1 piece) with HOLD directly below (empty = dashed outline;
  greyed 40% while unavailable per D19), TOP + SCORE, LEVEL; mascot panel bottom-right (D23); TOP updates
  live when score exceeds it (D21). Controls per D4 verbatim (arrows, ↑/X CW, Z/Ctrl CCW, Space hard drop,
  C/Shift hold, P/Esc pause, Enter menus). Audio engine: event→SFX map per D12 incl. "whistle REPLACES the
  ordinary clear pop on a 4-line clear" (D26) and whistle→bark +300 ms sequencing (D12); ducking per D26
  ("music drops to 60% volume and recovers linearly over 250 ms"); music per scene (D11). Particles per D13:
  sparkles on clearing rows, dust puff on hard drop, "KENJIRI!" text pop 0.6 s (D23). `__main__.py`: entry
  point + `--smoke` flag (init all systems, render one frame per scene offscreen, exit 0) for packaged-exe
  verification.
- **verify:** `uv run pytest tests/test_timing.py -q && uv run python -m kenjiri --smoke`
- **acceptance_criteria:**
  - FrameClock: elapsed 0.016 s→1 frame; 0.2 s→3 frames (clamped) with no auto-pause; 0.3 s→0 frames owed +
    `auto_pause_triggered` (D28 exact semantics).
  - `--smoke` exits 0 with dummy SDL drivers (headless CI-safe).
  - **Negative:** window resize/drag can never advance more than 3 logic frames per render frame (assert via
    FrameClock property test); no scene except gameplay ever triggers auto-pause (D28); rendering uses no
    smoothscale/bilinear calls (crisp pixels only, D16).
- **risk:** integration seams (event→audio/particle wiring) drift from ledger constants; blast radius = UX polish.

## T7 — packaging (wave 4, after T6)

- **owns:** `kenjiri.spec`, `tools/make_icon.py`, `assets/icon.ico`, `README.md`
- **read_first:** DECISIONS D1, D16, D23 (exe polish), D26, D28 (accepted onefile surface); T6's entry point.
- **action:** `tools/make_icon.py`: render the corgi `.ico` (16/32/48/256) from `gfx.sprites` pixel data
  (import, don't duplicate), deterministic, sha256 into assets/manifest.json is T2-owned — icon hash goes in
  README build notes instead (manifest.json is NOT yours). `kenjiri.spec` per D26 verbatim: "PyInstaller
  `--onefile --noconsole`"; bundle `assets/` as data; icon + version metadata v1.0.0 + window title "Kenjiri"
  (D23). README.md: what it is, controls table (D4), build (`uv sync`, `uv run python tools/make_assets.py`,
  `uv run pyinstaller kenjiri.spec`), run, high-score storage location, accepted PyInstaller %TEMP% note (D28).
- **verify:** `uv run pyinstaller kenjiri.spec --noconfirm && dist/kenjiri.exe --smoke`
- **acceptance_criteria:**
  - `dist/kenjiri.exe` exists, single file, has the corgi icon + v1.0.0 metadata; `--smoke` run exits 0.
  - **Negative:** launching the exe spawns NO console window (`--noconsole` in effect); the build pulls assets
    from the committed `assets/` (delete a generated temp dir first to prove no rebuild happens — D28
    "bundles them as-is and never re-renders").
- **risk:** packaging drift (missing data files) discovered only at exe launch; blast radius = the deliverable.
