"""SQLite-backed single-record high-score store (D15/D21/D24).

Schema: ``highscore(id INTEGER PRIMARY KEY CHECK(id=1), score, lines, level,
achieved_at)`` plus a ``schema_version`` table. All statements are
parameterized — SQL is never built via interpolation (D24). Degraded modes:

- DB absent/corrupt -> recreate fresh, log, don't crash (D15).
- DB locked/unwritable (or ``db_path=None``) -> session-only mode: nothing
  persists, ``top()`` serves the session best (D24/D28).
- ``submit()`` runs in a single transaction — no partial DB writes (D24).
"""
from __future__ import annotations

import datetime
import logging
import sqlite3
from pathlib import Path

_logger = logging.getLogger("kenjiri")

_SCHEMA_VERSION = 1

_SQL_CREATE_VERSION = "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
_SQL_CREATE_HIGHSCORE = (
    "CREATE TABLE IF NOT EXISTS highscore ("
    "id INTEGER PRIMARY KEY CHECK (id = 1), "
    "score INTEGER NOT NULL, "
    "lines INTEGER NOT NULL, "
    "level INTEGER NOT NULL, "
    "achieved_at TEXT NOT NULL)"
)
_SQL_SELECT_VERSION = "SELECT version FROM schema_version"
_SQL_INSERT_VERSION = "INSERT INTO schema_version (version) VALUES (?)"
_SQL_SELECT_TOP = "SELECT score, lines, level FROM highscore WHERE id = ?"
_SQL_UPSERT = (
    "INSERT INTO highscore (id, score, lines, level, achieved_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT (id) DO UPDATE SET "
    "score = excluded.score, lines = excluded.lines, "
    "level = excluded.level, achieved_at = excluded.achieved_at"
)


class HighScoreStore:
    """Single persisted TOP score with session-only degraded mode (D15/D21/D24)."""

    def __init__(self, db_path: Path | None) -> None:
        """Open (or recover) the store at ``db_path``.

        Args:
            db_path: SQLite file location, or ``None`` for session-only
                degraded mode (D24: play without persistence, session-best TOP).
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._session_best = 0
        self._cached_top = 0
        if db_path is not None:
            self._conn = self._open_or_recover(db_path)
            if self._conn is not None:
                try:
                    self._cached_top = self._read_top()
                except sqlite3.Error:
                    _logger.warning("high-score DB unreadable; session-only mode (D24)")
                    self._degrade()

    def top(self) -> int:
        """Return the TOP score to display.

        The persisted record when available; in degraded/session-only mode
        this serves the session best (D24/D28).
        """
        return max(self._cached_top, self._session_best)

    def submit(self, score: int, lines: int, level: int) -> bool:
        """Submit a finished game's result (persist point = top-out, D21).

        Persists — in a single transaction (D24: no partial DB writes) —
        only when ``score`` exceeds the stored top, and returns ``True``
        only then (D21). In session-only mode nothing persists and this
        returns ``False``, but the session best still updates for
        :meth:`top`.

        Args:
            score: Final score of the run.
            lines: Total lines cleared.
            level: Level reached.

        Returns:
            ``True`` when a new record was persisted, else ``False``.
        """
        persisted = False
        if self._conn is not None:
            try:
                with self._conn:
                    row = self._conn.execute(_SQL_SELECT_TOP, (1,)).fetchone()
                    stored = int(row[0]) if row is not None else 0
                    if score > stored:
                        self._conn.execute(
                            _SQL_UPSERT, (1, score, lines, level, self._now())
                        )
                        persisted = True
            except sqlite3.Error:
                _logger.warning(
                    "high-score write failed; session-only mode for this run (D24)"
                )
                self._degrade()
                persisted = False
            else:
                if persisted:
                    self._cached_top = score
        if score > self._session_best:
            self._session_best = score
        return persisted

    def close(self) -> None:
        """Close the underlying connection (idempotent)."""
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    # ------------------------------------------------------------- internal

    def _degrade(self) -> None:
        """Drop to session-only mode, keeping the last known persisted top."""
        self.close()

    def _now(self) -> str:
        """Return the current UTC timestamp in ISO-8601 form."""
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _read_top(self) -> int:
        """Read the persisted top score (0 when no record exists)."""
        assert self._conn is not None
        row = self._conn.execute(_SQL_SELECT_TOP, (1,)).fetchone()
        return int(row[0]) if row is not None else 0

    def _open_or_recover(self, path: Path) -> sqlite3.Connection | None:
        """Open the DB, recreating a corrupt file (D15) or degrading (D24).

        Order matters: ``sqlite3.OperationalError`` (locked/unwritable — must
        NOT delete a valid DB) is a subclass of ``sqlite3.DatabaseError``
        (corrupt — safe to recreate), so it is caught first.
        """
        try:
            return self._connect(path)
        except sqlite3.OperationalError:
            _logger.warning("high-score DB locked/unwritable; session-only mode (D24)")
            return None
        except sqlite3.DatabaseError:
            _logger.warning("high-score DB corrupt; recreating fresh (D15)")
            try:
                path.unlink(missing_ok=True)
                return self._connect(path)
            except (sqlite3.Error, OSError):
                _logger.warning(
                    "high-score DB recreate failed; session-only mode (D24)"
                )
                return None
        except OSError:
            _logger.warning("high-score DB unopenable; session-only mode (D24)")
            return None

    def _connect(self, path: Path) -> sqlite3.Connection:
        """Connect and ensure the versioned schema exists (single transaction).

        Raises:
            sqlite3.DatabaseError: File is not a database or its schema
                version is unsupported (caller recreates fresh per D15).
            sqlite3.OperationalError: DB locked/unwritable (caller degrades).
        """
        conn = sqlite3.connect(path)
        try:
            with conn:
                conn.execute(_SQL_CREATE_VERSION)
                conn.execute(_SQL_CREATE_HIGHSCORE)
                row = conn.execute(_SQL_SELECT_VERSION).fetchone()
                if row is None:
                    conn.execute(_SQL_INSERT_VERSION, (_SCHEMA_VERSION,))
                elif int(row[0]) != _SCHEMA_VERSION:
                    raise sqlite3.DatabaseError(
                        "unsupported high-score schema version"
                    )
        except BaseException:
            conn.close()  # release the file handle before any unlink (Windows)
            raise
        return conn
