---
kind: project
goal: 'Ship Kenjiri: a polished, one-shot-built NES-style Tetris clone for Windows
  desktop that proves KataHarness can one-shot high-quality software. Pastel chibi
  corgi theme throughout: corgi title screen with KENJIRI logo and Start, SNES Tetris
  & Dr. Mario gameplay layout (per-piece statistics, lines, next, score/top/level)
  recolored pastel, accurate Tetris physics (guideline PC controls, 7-bag, SRS, DAS/ARR
  feel, NES scoring, linear no-cliff gravity ramp), three original chiptune tracks,
  corgi-themed SFX, line-clear sparkles and hard-drop dust, a corner chibi corgi mascot
  with emote reactions, SQLite-persisted high score, 256x240 integer-scaled resizable
  window, shipped as a single kenjiri.exe.'
fixes: []
features:
- 'Corgi title screen: KENJIRI striped logo, chibi pixel corgi, PUSH START, title
  theme'
- 'Standard game: 10x20 field, 7 pastel pieces, 7-bag, SRS CW/CCW, hold, ghost, next
  preview'
- 'Guideline PC controls: arrows move/soft-drop, Up/X CW, Z/Ctrl CCW, Space hard drop,
  C/Shift hold, P/Esc pause'
- 'SNES-style HUD: per-piece counters, LINES, NEXT, SCORE, TOP (high score), LEVEL'
- NES scoring 40/100/300/1200 x (level+1); Kenjiri = 4-line clear; level per 10 lines
- Linear gravity ramp ~48 frames/row at L0 to ~4-frame floor (no killscreen cliff)
- Three original chiptune tracks (title, gameplay, game over) - no Korobeiniki
- 'Corgi SFX: lock thud, hard-drop slam, clear pop, dog-whistle Kenjiri, bark level-up
  fanfare, sad whine on top-out'
- 'Particles: sparkle/stars on cleared blocks, transparent dust puff on hard drop'
- Corner chibi corgi mascot with emote animations (idle/happy/hype/sad)
- High score persisted in local SQLite
- 256x240 canvas, crisp integer scaling, default 3x (768x720), resizable window
- Packaged as single-file kenjiri.exe (PyInstaller)
modulesAdded: []
changeSummary: Greenfield build of Kenjiri, a corgi-themed NES-style Tetris clone
  shipped as a Windows exe.
target:
  kind: greenfield
  path: C:\Users\taurr_nvs748q\PokeVault\PokeVault\projects\kenjiri
  vault: own:C:\Users\taurr_nvs748q\PokeVault\PokeVault
  platform: claude
grillDepth: full
readiness: 'READY. Advanced-depth grill converged: 28 locked ledger entries (D1-D28)
  covering ruleset blend, controls/handling constants, linear gravity formula, scoring,
  matrix geometry incl. block-out/lock-out, HUD/title composition, audio scope, particles,
  mascot, persistence, packaging, timing-stall policy, security posture and degraded
  modes. Double fresh-context convergence gate: pass 1 (main tree) HOLD->fixed->SHIP;
  pass 2 (security/edge layer) HOLD->fixed->SHIP. Dependency manifest approved at
  freeze (pygame-ce, numpy, pyinstaller, pytest via pypi/uv; snyk CLI on host). Deferred
  to in-loop: artistic latitude only (exact sprite pixels, melody notes) plus kata-defer
  assumption logging; no decision branches remain open.'
acceptanceCriteria:
- kenjiri.exe launches windowed on Windows 11 showing the corgi title screen (KENJIRI
  logo, chibi corgi, Start) with title music
- 'Start begins a standard game: 10x20 field, 7 pastel pieces, 7-bag randomizer, SRS
  rotation both directions, hold, ghost piece, next preview'
- Controls match the PC guideline standard (arrows, Up/X, Z/Ctrl, Space hard drop,
  C/Shift hold) with DAS ~167ms / ARR ~33ms; P or Esc pauses
- HUD shows per-piece statistics counters, LINES, NEXT, SCORE, TOP and LEVEL in the
  SNES layout, pastel corgi theme
- Scoring is NES-accurate (40/100/300/1200 x level+1); level rises every 10 lines;
  gravity ramps linearly with no cliff to a ~4-frame floor
- Top-out shows a game-over screen with score, sad whine SFX and the game-over theme
- High score persists in a local SQLite DB across restarts and displays as TOP
- Three distinct original chiptune tracks play (title, gameplay, game over); none
  is the Tetris theme
- Corgi SFX fire on lock, hard drop, line clear, Kenjiri (dog whistle), level up (bark
  fanfare) and top-out (sad whine)
- Line clears show sparkle particles; hard drops show a transparent dust puff
- A corner chibi corgi mascot animates emotes reacting to line clears, Kenjiris, level-ups
  and top-out
- Window scales crisply (integer scaling) from the 256x240 canvas, default 3x
- pytest suite green covering board, rotation, bag, scoring, gravity and persistence
  logic
- Snyk scan on the new code reports no new issues
---

# North-Star Intent

## Goal

Ship Kenjiri: a polished, one-shot-built NES-style Tetris clone for Windows desktop that proves KataHarness can one-shot high-quality software. Pastel chibi corgi theme throughout: corgi title screen with KENJIRI logo and Start, SNES Tetris & Dr. Mario gameplay layout (per-piece statistics, lines, next, score/top/level) recolored pastel, accurate Tetris physics (guideline PC controls, 7-bag, SRS, DAS/ARR feel, NES scoring, linear no-cliff gravity ramp), three original chiptune tracks, corgi-themed SFX, line-clear sparkles and hard-drop dust, a corner chibi corgi mascot with emote reactions, SQLite-persisted high score, 256x240 integer-scaled resizable window, shipped as a single kenjiri.exe.

## Change Summary

Greenfield build of Kenjiri, a corgi-themed NES-style Tetris clone shipped as a Windows exe.

## Notes

- **Run kind:** `project`
- This file was frozen by `kata-initiate` at the end of the initiation
  session.  It is the authoritative goal record for this run.
- Do **not** modify this file mid-run.  If a discovery invalidates the
  goal, treat it as an escalation event (`protocol/escalation.md`).
