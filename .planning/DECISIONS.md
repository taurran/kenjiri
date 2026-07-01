# Kenjiri — Decision Ledger (kata-grill-standard)

Grill session 2026-07-01. Entries per [[kata-grill]] RUBRIC / DECISION-LEDGER format.
LOCKED = frozen; re-deciding downstream is drift.

### D1 — Tech stack · LOCKED
- **Question:** What stack ships a Windows exe of an 8-bit style game fastest at one-shot quality?
- **Provenance:** INTENT requirement "must be an executable file in Windows"; operator's uv/Python environment.
- **Options considered:** A (chosen) Python + pygame-ce + PyInstaller — fast dev, fits operator toolchain, ~30MB exe · B Rust/macroquad — tiny exe, slower dev · C Love2D — fine, but non-Python toolchain.
- **Decision:** Python 3.12 via uv; pygame-ce for render/input/audio; PyInstaller --onefile for `kenjiri.exe`; numpy for offline audio synthesis; sqlite3 (stdlib) for persistence; pytest for tests.
- **Rationale:** Operator's standing standards (uv, pytest, type hints); one-shot risk lowest on the best-known path.
- **Edges/scenarios:** PyInstaller AV false-positive risk accepted (personal project); exe is onefile — first-launch unpack delay ~1–2s accepted.
- **Doc-baked:** dependency manifest below.

### D2 — Target, vault, platform · LOCKED
- **Question:** Where does the project live and what drives the run?
- **Provenance:** Operator instruction 2026-07-01.
- **Decision:** Greenfield at `C:\Users\taurr_nvs748q\PokeVault\PokeVault\projects\kenjiri`; vault = that PokeVault instance; platform = Claude, single-host; this location is the new default for future projects (written to `.kata-settings.json`).
- **Edges/scenarios:** Vault is itself a git repo → project repo is nested; vault `.gitignore` gains `projects/kenjiri/` (operator approved).
- **Doc-baked:** kata settings updated; memory saved.

### D3 — Ruleset blend · LOCKED
- **Question:** Classic NES rules or modern guideline?
- **Provenance:** howtotetris.com describes modern; operator's SNES longplay is classic; operator: "go with whatever rules make sense... accurate to the physics of the real thing."
- **Options considered:** A (chosen) modern guideline mechanics + NES scoring/feel · B pure NES classic (no hold/ghost/hard drop) · C pure modern guideline incl. guideline scoring.
- **Decision:** 7-bag randomizer, SRS rotation with wall kicks (CW + CCW), hold (one swap per piece), ghost piece, hard + soft drop, next preview — with NES scoring table and level cadence (D6/D7).
- **Rationale:** "Standard Tetris" as played on PC today is guideline; NES scoring/curve preserves the retro feel the operator wants.
- **Edges/scenarios:** Hold locked until current piece locks (guideline standard); no T-spin bonus scoring, no combos, no garbage (single-player, NES scoring model — T-spins still *work* mechanically via SRS, they just score as normal clears).

### D4 — Controls · LOCKED
- **Question:** Key mapping for PC play.
- **Provenance:** Operator asked to match PC-standard Tetris; verified vs tetris.wiki Tetris Guideline.
- **Decision:** ←/→ shift; ↓ soft drop (non-locking); ↑ or X rotate CW; Z or Ctrl rotate CCW; Space hard drop (locking); C or Shift hold; P or Esc pause. Enter = confirm on menus.
- **Rationale:** Exact guideline keyboard standard; Space-as-pause rejected because Space is universally hard drop (operator accepted P/Esc).
- **Edges/scenarios:** Keys ignored during line-clear animation except pause; pause during fall freezes gravity, DAS state cleared on unpause to prevent slide-on-resume.

### D5 — Handling feel (DAS/ARR) · LOCKED
- **Question:** Auto-shift timing magnitudes.
- **Provenance:** tetris.wiki guideline recommended handling.
- **Decision:** DAS 167 ms initial delay, ARR 33 ms repeat (10/2 frames at 60fps); soft drop = 20× current gravity (capped at 1 row/frame); implemented frame-rate independent.
- **Edges/scenarios:** Direction change mid-DAS resets the charge; DAS charge held through hard drop into next piece spawn (modern feel).

### D6 — Gravity curve · LOCKED
- **Question:** Level speed arc — authentic NES cliff or fun-first?
- **Provenance:** tetris.wiki NES ROM table (48/43/38/…/2/1 with cliff at L29); operator: "leave out the cliff, more linear, more fun."
- **Options considered:** A (chosen) linear ramp 48 − 3·level, floor 4 · B authentic NES table incl. cliff · C guideline Tetris-Worlds exponential formula.
- **Decision:** `framesPerRow(level) = max(48 − 3·level, 4)` at 60 fps reference (0.8 s/row at L0 → 4-frame floor ≈ 0.067 s/row from L15 on). Level advances every 10 lines, unbounded, speed capped at the floor.
- **Rationale:** Preserves NES level-0 pacing and early arc, removes the 8→6→5 cliff and the L29 killscreen per operator intent.
- **Edges/scenarios:** L14 = 6 frames, L15+ = 4 frames (floor); soft drop at floor = 1 row/frame cap; gravity accumulator handles fractional rows for frame-rate independence.

### D7 — Scoring · LOCKED
- **Question:** Points model.
- **Provenance:** Operator: points for line clears; NES scoring verified via tetris.wiki.
- **Decision:** Single 40 · Double 100 · Triple 300 · **Kenjiri (4 lines) 1200**, each × (level + 1). Soft drop +1/row while held; hard drop +2/row dropped. No combo/B2B/T-spin bonuses.
- **Edges/scenarios:** Score awarded at lock using level *before* any level-up from that clear (NES behavior); score display 7 digits, caps at 9,999,999 without overflow.

### D8 — HUD layout · LOCKED
- **Question:** Gameplay screen composition.
- **Provenance:** Operator's SNES Tetris & Dr. Mario reference screenshot (reviewed).
- **Decision:** Left panel: STATISTICS — all 7 piece glyphs with running spawn counters. Top-center: LINES-NNN. Right column top-to-bottom: NEXT box, TOP (persisted high score) + SCORE, LEVEL. Playfield center 10×20. Pastel chibi-corgi recolor of the SNES gold/brick framing.
- **Edges/scenarios:** Counters count *spawned* pieces (incl. held-then-swapped ones — counted once at spawn); counters cap at 999.

### D9 — Title screen · LOCKED
- **Question:** Composition.
- **Provenance:** Operator's NES title reference + chibi corgi reference (both reviewed).
- **Decision:** Striped KENJIRI logo (NES-style lettering), chibi pixel corgi (orange/cream, collar, tongue out) where St. Basil's sat, "PUSH START" prompt (Enter/click/Space all start), tetromino-brick border, title theme playing.
- **Edges/scenarios:** Start transitions with short jingle/fade < 1 s into gameplay at level 0.

### D10 — Palette · LOCKED
- **Decision:** Pastel versions of standard piece hues: I soft-aqua, L peach, J periwinkle, S mint, Z blush-rose, O butter-yellow, T lavender; cream/warm-orange/pink/mint UI framing; bright, chibi, Japanese-kawaii tone.

### D11 — Audio: music · LOCKED
- **Question:** Soundtrack scope and sourcing.
- **Provenance:** Operator wants 3 original 8-bit songs (title / gameplay / game-over), NOT the Tetris theme; referenced KEXP video is unviewable (metadata confirmed only) — melodies are original, "weird" in spirit (odd intervals, shifting meter).
- **Decision:** NES-APU-style synth (2 pulse + triangle + noise channels) written as a reproducible Python script in `tools/`; renders OGG assets at build time from note-data tables; gameplay loop ~60–90 s, title loop ~30–45 s, game-over ~15–20 s bittersweet-resolving-warm. Korobeiniki explicitly avoided (also trademark-safe).
- **Edges/scenarios:** Music volume ducks under SFX; pause lowers music volume 50%; tracks loop seamlessly.

### D12 — Audio: SFX · LOCKED
- **Decision:** Corgi-chibi 8/16-bit SFX set, same synth: soft thud (lock), heavier slam (hard drop), pop (line clear), rising dog-whistle (Kenjiri), excited bark fanfare (level up), sad puppy "awwh" whine (top-out), menu blip (UI). All synthesized, all on-theme.
- **Edges/scenarios:** Simultaneous events (level-up + Kenjiri same lock) → whistle plays, bark fanfare follows 300 ms later; SFX never stack-clip (per-channel management).

### D13 — Particles & juice · LOCKED
- **Decision:** Star/sparkle burst on clearing blocks during the ~0.3 s clear animation; transparent dust puff at landing row on hard drop; "KENJIRI!" text pop on a quad. Per-pixel-alpha surfaces in pygame.

### D14 — Corgi mascot · LOCKED
- **Question:** Include animated corner mascot?
- **Provenance:** Operator: "only if you are highly confident."
- **Decision:** IN. Small pixel chibi corgi in a corner panel; emote states: idle (tail wag loop), happy (line clear), hype (Kenjiri/level-up, ears up), sad (top-out, droopy). Sprite-frame swaps driven by game events — low-risk.

### D15 — High-score persistence · LOCKED (score shape + display rule refined by D21, which supersedes on conflict)
- **Decision:** SQLite via stdlib `sqlite3`, DB at `%LOCALAPPDATA%\Kenjiri\kenjiri.db` (exe dir may be unwritable); schema versioned; TOP on HUD reads it at game start, updates on new record at game over.
- **Edges/scenarios:** DB absent/corrupt → recreate fresh (log, don't crash); concurrent instances → last-writer-wins acceptable (single-player desktop).

### D16 — Window & scaling · LOCKED
- **Decision:** Internal canvas 256×240 (NES resolution); default window 3× (768×720); free resize allowed — render letterboxed at the largest integer scale that fits; nearest-neighbor only (crisp pixels); windowed mode only.
- **Edges/scenarios:** Minimum window 1× (256×240); odd sizes letterbox with theme-colored bars.

### D17 — Quality gates · LOCKED
- **Decision:** pytest suite for board/rotation/bag/scoring/gravity/persistence (written alongside code); Snyk code scan on new first-party code, fix-and-rescan loop until clean; kata-evaluate fresh-context default-FAIL gate before done.

### Dependency manifest (per protocol/dependencies.md)
- `pygame-ce` (runtime: render/input/audio) — PyPI
- `numpy` (build-time audio synth) — PyPI
- `pyinstaller` (packaging) — PyPI
- `pytest` (dev/test) — PyPI
- `snyk` CLI (security gate) — already installed on host
- Python 3.12 via `uv` — present

### D18 — Lock delay · LOCKED
- **Question:** Instant NES lock vs modern grace window.
- **Provenance:** D3 ruleset blend left landing feel open; operator round-1 answer A.
- **Options considered:** A (chosen) 0.5 s lock delay with move/rotate reset, capped · B instant lock.
- **Decision:** 0.5 s lock delay; any successful move/rotate while grounded resets it, max 15 resets per piece, then force-lock on next ground contact. Hard drop locks instantly.
- **Edges/scenarios:** Reset counter clears when the piece falls to a new lowest row; at floor gravity (4 frames/row) the delay still applies — the game stays fair at speed; soft drop onto ground does not skip the delay, hard drop does.

### D19 — NEXT preview + HOLD placement · LOCKED
- **Provenance:** SNES reference shows 1-piece NEXT, no hold; operator round-1 answer A.
- **Decision:** 1-piece NEXT box top-right (faithful to reference); HOLD box directly below NEXT showing the stashed piece glyph (empty = dashed outline); both boxes same pastel framing.
- **Edges/scenarios:** Hold swap updates both boxes same frame; held piece renders in its pastel color, greyed 40% until hold re-enables at next lock (visual affordance for the once-per-piece rule, D3).

### D20 — Starting level · LOCKED
- **Provenance:** Operator round-1 answer A.
- **Decision:** Start always begins at level 0. No selector. Title keeps single PUSH START affordance.

### D21 — High-score shape · LOCKED
- **Provenance:** Operator round-1 answer A ("a high score", singular, satisfied by simplest model).
- **Decision:** Single persisted TOP score (schema: `highscore(id=1, score, lines, level, achieved_at)`). HUD TOP updates live when current score exceeds it; game-over screen shows "NEW TOP!" banner when the record was beaten and persists it then.
- **Edges/scenarios:** Closing the window mid-game does NOT persist the in-progress score (persist point = top-out only) — accepted; DB absent/corrupt → recreate (D15); no initials entry exists, so no text-input surface.

### D22 — Git/GitHub timing · LOCKED
- **Provenance:** Operator round-1 answer A; standing rule "remind to init GitHub repo" satisfied this session.
- **Decision:** `git init` at project seed (harness gates against a clean repo); GitHub remote created at closeout, operator picks public/private then. Vault `.gitignore` gains `projects/kenjiri/`.

### D23 — Derived branches (re-derivation sweep, self-resolved) · LOCKED
- **Pause screen:** field dims 60% under a "PAWSED" panel with paw icon; music volume −50%; gravity, lock delay, DAS and animations all frozen; P/Esc resumes; DAS charge cleared on resume (D4).
- **Line-clear animation:** ~0.3 s — filled rows flash white→sparkle burst (D13) → collapse; input except pause ignored during it; no additional ARE beyond it.
- **Game-over screen:** dark pastel panel over the field: SCORE / LINES / LEVEL, TOP with "NEW TOP!" banner if beaten, sad-whine SFX then game-over theme once; Enter/click returns to title. Mascot plays sad emote.
- **Kenjiri text pop:** "KENJIRI!" pixel text pops center-field on a quad (D13), 0.6 s.
- **Timing model:** fixed-timestep 60 Hz logic with frame-rate-independent accumulator; render vsync'd; gravity/DAS/lock-delay all expressed in 60 fps reference frames (D5/D6).
- **Project structure:** src/ layout per operator standards — `src/kenjiri/` (`game/` core logic, `ui/` scenes+HUD, `gfx/` sprites+particles, `audio/`, `persistence/`), `tools/synth.py` + `tools/make_assets.py` (reproducible asset generation), `assets/` (generated OGG/PNG committed), `tests/`, `pyproject.toml` (uv), type hints + docstrings throughout.
- **Exe polish:** corgi `.ico` window/exe icon; version metadata v1.0.0; window title "Kenjiri".
- **Mascot placement:** bottom-right corner panel below LEVEL box (only free quadrant in the SNES layout).

### D24 — Security surface & degraded modes (advanced pass) · LOCKED
- **Threat model:** fully offline single-player desktop app — no network, no auth, no PII. Data at rest = one local SQLite file of game scores.
- **Decisions:** SQLite access via parameterized queries only; DB path built with `pathlib` under `%LOCALAPPDATA%\Kenjiri` (no shell interpolation, no user-supplied paths); no `eval`/`exec`/pickle; no text input surfaces exist (D21A closed the initials branch); dependencies pinned via `uv.lock`; PyInstaller builds from the locked env (supply-chain hygiene); Snyk code scan gate per D17.
- **Degraded modes:** audio device/mixer init failure → run silent, log once, never crash; DB locked/unwritable → play without persistence, TOP shows session-best, log once; display smaller than 256×240 → clamp to 1× with scrollbars-free letterbox.
- **Edges (combinatorial sweep):** hold+hard-drop same frame → hold wins if pressed first (input queue order); pause during line-clear → allowed, freezes animation; resize mid-clear → re-letterbox, state intact; Kenjiri + level-up + new-TOP same lock → SFX sequence whistle → bark (+300 ms) with TOP banner deferred to game over; Alt-F4 → clean pygame quit, no partial DB writes (single transaction at top-out).

### D25 — Matrix geometry, spawn, and top-out semantics · LOCKED
- **Question:** Where do pieces spawn, do hidden rows exist, and exactly when is the game over? (Convergence pass 1, MATERIAL finding.)
- **Provenance:** D3 blended NES + guideline without fixing the matrix; SRS/lock-delay/top-out all presuppose this.
- **Options considered:** A (chosen) guideline matrix — 10×20 visible + hidden buffer rows above · B NES-style spawn inside the visible field, no buffer.
- **Decision:** Matrix is 10×22: rows 1–20 visible, rows 21–22 a hidden buffer (vanish zone — cells there exist but render nothing). Pieces spawn per guideline: horizontal, flat-side down, centered-left (J/L/S/Z/T occupy columns 4–6, I and O centered on columns 4–7), resting on rows 21–22 so they enter the visible field by falling. SRS rotation/kicks operate in the full 22-row matrix, including above the ceiling. Two top-out conditions, both = game over: **block-out** (a spawning piece overlaps an existing block) and **lock-out** (a piece locks with ALL its cells above row 20). A piece locking partially above row 20 is legal; its buffer-row cells persist invisibly and can be cleared like any others.
- **Rationale:** The guideline matrix is what every modern PC Tetris uses and what the chosen SRS + lock-delay mechanics assume; NES-style visible spawn would fight them at the ceiling.
- **Edges/scenarios:** Rotation kicks may push a piece into the buffer at the ceiling — legal; a line clear in a buffer row is possible and scores normally; ghost piece is not drawn while the falling piece is entirely in the buffer; game-over check order at spawn = block-out first, then normal play.

### D26 — Convergence pass 1: minor-finding resolutions · LOCKED
- **ARE (non-clearing lock):** none — next piece spawns on the next logic frame after lock (modern feel, consistent with D5's DAS-carry rule).
- **DAS across line-clear:** a held direction retains its full DAS charge through the clear animation into the next spawn (same principle as D5 hard-drop carry).
- **Kenjiri SFX layering:** the dog whistle REPLACES the ordinary clear pop on a 4-line clear (it is the quad's sound, not an overlay).
- **Music duck:** on any SFX, music drops to 60% volume and recovers linearly over 250 ms.
- **LINES display:** grows from 3 to 4 digits past 999; clamps at 9999 (counter keeps counting internally).
- **Quit paths:** pause panel text "P/ESC RESUME · Q QUIT TO TITLE" (Q from pause abandons the run — score NOT persisted, consistent with D21 persist-point); Esc on the title screen exits the app cleanly.
- **Packaging:** PyInstaller `--onefile --noconsole` — no console window behind the game.

### D27 — Convergence pass 1 re-check: residual pins · LOCKED
- **Spawn rows exact:** I spawns in row 21 (its single row); O occupies columns 5–6, rows 21–22; all other pieces occupy columns 4–6, rows 21–22 (flat-side down).
- **Immediate spawn drop (guideline standard):** on the spawn frame, if the cell below is free, the piece immediately falls one row — so a spawning piece's lower cells reach visible row 20 at once; no invisible dead-time at low levels. Block-out is checked at the spawn position *before* this drop.
- **DAS during clear animation:** a held direction's DAS charge *continues accruing* during the line-clear animation (it does not freeze), capped at full charge. (Refines D4's "keys ignored during clear" — input *events* are ignored, held *state* keeps being sampled; D27 supersedes on conflict.)

### D28 — Convergence pass 2: timing stalls, security posture, degraded-mode completions · LOCKED
- **Question:** What happens to owed logic frames when Windows blocks the loop (window drag/resize/minimize), plus five security/degraded-mode gaps. (Convergence pass 2: 1 MATERIAL, 5 MINOR.)
- **Timing stall policy (MATERIAL fix):** the fixed-timestep accumulator is **clamped to a maximum catch-up of 3 logic frames (50 ms) per render frame**; any measured frame gap > 250 ms discards the excess time and **auto-pauses** the game (PAWSED panel, standard resume). The game also auto-pauses on window focus loss and minimize. Net effect: dragging/resizing the window can never advance gravity, expire lock delay, fire DAS bursts, or complete the clear animation unseen — this is the binding definition of D24's "state intact."
- **Asset pipeline canonicality:** the **committed** files in `assets/` are canonical; PyInstaller bundles them as-is and never re-renders. `tools/make_assets.py` is deterministic (fixed RNG seed, no timestamps embedded); a pytest asserts that regenerating assets reproduces the committed content hashes, so a synth edit without regeneration fails the suite.
- **`%LOCALAPPDATA%` unresolvable:** treated exactly as DB-unwritable (D24): play without persistence, session-best TOP, log once. Never fall back to a relative/CWD path.
- **Log sink:** `%LOCALAPPDATA%\Kenjiri\kenjiri.log` (append, truncate above 1 MB); with `--noconsole` there is no stdout/stderr, so the file is the only sink; if the log path itself is unavailable, logging disables silently — degraded modes must never crash the game they're protecting.
- **PyInstaller onefile surface — explicitly accepted:** `--onefile` self-extracts to per-user `%TEMP%\_MEIxxxxxx` at launch (historic DLL-planting class, cf. CVE-2019-16784). Accepted for a single-user personal game on Windows 11 with PyInstaller pinned current via `uv.lock`. Recorded, not ignored.
- **Snyk gate widened:** D17's gate = Snyk **code** scan AND **SCA dependency** scan (uv.lock makes SCA trivial); both clean before done.
- **Auto-pause scope (pass-2 re-check nit):** auto-pause applies to the gameplay scene only; title and game-over scenes hold no time-sensitive state and never show the PAWSED panel.
