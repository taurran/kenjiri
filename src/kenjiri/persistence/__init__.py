"""Kenjiri persistence layer: paths, degraded-mode logging, high-score store.

Everything here is pure stdlib (``sqlite3``, ``pathlib``, ``logging``,
``os``) and honors the degraded-mode ledger: unresolvable %LOCALAPPDATA%
or an unwritable DB means the game plays without persistence — never a
crash, never a CWD fallback (D15/D24/D28).
"""
from kenjiri.persistence.applog import get_logger
from kenjiri.persistence.highscore import HighScoreStore
from kenjiri.persistence.paths import data_dir, db_path, log_path

__all__ = [
    "HighScoreStore",
    "data_dir",
    "db_path",
    "get_logger",
    "log_path",
]
