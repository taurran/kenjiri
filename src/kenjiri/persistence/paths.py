"""Filesystem path resolution for Kenjiri persistence (D24/D28).

Resolves ``%LOCALAPPDATA%\\Kenjiri`` via ``os.environ`` + ``pathlib`` only —
no shell interpolation, no user-supplied paths (D24). When LOCALAPPDATA is
missing, empty, relative, or the directory cannot be created, every function
returns ``None`` and a warning is logged once: the game plays without
persistence with a session-best TOP. It NEVER falls back to a relative or
CWD path (D28).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Mapping

_APP_DIR_NAME = "Kenjiri"
_DB_FILENAME = "kenjiri.db"
_LOG_FILENAME = "kenjiri.log"

_logger = logging.getLogger("kenjiri")
_warned_unresolvable = False


def _warn_once(message: str) -> None:
    """Log the unresolvable-path warning at most once per process (D28)."""
    global _warned_unresolvable
    if not _warned_unresolvable:
        _warned_unresolvable = True
        _logger.warning(message)


def data_dir(env: Mapping[str, str] | None = None) -> Path | None:
    """Resolve and create the Kenjiri data directory under %LOCALAPPDATA%.

    Args:
        env: Environment mapping to resolve from; defaults to ``os.environ``
            (injectable for tests so the real %LOCALAPPDATA% is never touched).

    Returns:
        The absolute ``%LOCALAPPDATA%\\Kenjiri`` directory (created if needed),
        or ``None`` when LOCALAPPDATA is missing/empty/relative or the
        directory cannot be created (D28: treated as DB-unwritable).
    """
    source: Mapping[str, str] = os.environ if env is None else env
    raw = source.get("LOCALAPPDATA", "")
    if not raw:
        _warn_once(
            "LOCALAPPDATA unresolvable; playing without persistence (session-best TOP)"
        )
        return None
    base = Path(raw)
    if not base.is_absolute():
        _warn_once(
            "LOCALAPPDATA is not an absolute path; refusing relative/CWD fallback (D28); "
            "playing without persistence (session-best TOP)"
        )
        return None
    target = base / _APP_DIR_NAME
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        _warn_once(
            "cannot create data directory under LOCALAPPDATA; "
            "playing without persistence (session-best TOP)"
        )
        return None
    return target


def db_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the high-score database path, or ``None`` when unresolvable.

    Args:
        env: Optional environment mapping override (testability injection).

    Returns:
        ``%LOCALAPPDATA%\\Kenjiri\\kenjiri.db`` or ``None`` per :func:`data_dir`.
    """
    base = data_dir(env)
    return None if base is None else base / _DB_FILENAME


def log_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the application log path, or ``None`` when unresolvable.

    Args:
        env: Optional environment mapping override (testability injection).

    Returns:
        ``%LOCALAPPDATA%\\Kenjiri\\kenjiri.log`` or ``None`` per :func:`data_dir`.
    """
    base = data_dir(env)
    return None if base is None else base / _LOG_FILENAME
