# Kenjiri — CONTEXT (glossary)

Canonical terms for this project. _Avoid_ lists banned synonyms.

- **Kenjiri** — (1) the game; (2) a 4-line clear, worth 1200 × (level+1). _Avoid:_ "Tetris" for the 4-line clear.
- **Piece** — one of the 7 tetrominoes (I, O, T, S, Z, J, L). _Avoid:_ mino, tetrad, block (block = one cell of a piece).
- **Field** — the playfield: 10×22 matrix, rows 1–20 visible. _Avoid:_ board, well.
- **Buffer** — hidden rows 21–22 above the visible field (vanish zone); cells exist, render nothing. _Avoid:_ vanish zone as a distinct term.
- **Bag** — the 7-bag randomizer: each set of 7 pieces contains every piece exactly once, shuffled.
- **Gravity** — automatic fall rate, defined as frames-per-row at a 60 fps reference; `max(48 − 3·level, 4)`.
- **Lock** — the moment a piece becomes part of the field.
- **Soft drop** — held ↓, 20× gravity, non-locking, +1 point/row.
- **Hard drop** — Space, instant drop and lock, +2 points/row.
- **Hold** — stash the falling piece (C/Shift); one swap per piece; re-enabled at next lock.
- **Ghost** — translucent preview of where the falling piece would land.
- **Next** — preview of upcoming piece(s) from the bag.
- **Statistics** — the per-piece spawn counters panel (left side of HUD, SNES-style).
- **TOP** — the persisted high score shown on the HUD (from local SQLite).
- **Top-out** — game over, via either **block-out** (spawning piece overlaps a block) or **lock-out** (piece locks entirely above row 20). _Avoid:_ "death", "kill".
- **Mascot** — the corner chibi corgi sprite with emote states (idle/happy/hype/sad).
- **Canvas** — the 256×240 internal render surface, integer-scaled to the window.
