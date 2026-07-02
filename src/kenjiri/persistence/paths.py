"""Filesystem path resolution for Kenjiri persistence (D24/D28).

Resolves the per-user Kenjiri data directory via ``os.environ`` + ``pathlib``
only — no shell interpolation, no user-supplied paths (D24):

- **Windows:** ``%LOCALAPPDATA%\\Kenjiri``
- **macOS:** ``~/Library/Application Support/Kenjiri``

When the base location is missing, empty, relative, or the directory cannot be
created, every function returns ``None`` and a warning is logged once: the game
plays without persistence with a session-best TOP. It NEVER falls back to a
relative or CWD path (D28).

The ``env`` parameter stays meaningful on both platforms so tests can inject a
sandbox base and never touch the real user directory: an injected
``LOCALAPPDATA`` selects the Windows resolver (from any host), otherwise the
macOS resolver reads ``HOME`` from the same injected mapping.
"""
from __future__ import annotations

import logging
import os
import sys
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


def _app_dir(base_raw: str, label: str) -> Path | None:
    """Resolve and create ``<base_raw>/Kenjiri`` behind the D24/D28 guards.

    Shared by both platform resolvers so every guarantee is identical: the
    base must be a non-empty, clean, absolute path; the app dir must stay a
    direct child of the resolved base (CWE-23 containment); creation failure
    yields ``None``. ``label`` names the base in the log message.

    Args:
        base_raw: The platform base directory (``%LOCALAPPDATA%`` on Windows,
            ``~/Library/Application Support`` on macOS) as a raw string.
        label: Human-readable name of the base for the once-logged warning.

    Returns:
        The absolute ``<base_raw>/Kenjiri`` directory (created if needed), or
        ``None`` when the base is missing/empty/relative or the directory
        cannot be created (D28: treated as DB-unwritable).
    """
    if not base_raw:
        _warn_once(
            f"{label} unresolvable; playing without persistence (session-best TOP)"
        )
        return None
    base = Path(base_raw)
    if not base.is_absolute() or any(part == ".." for part in base.parts):
        _warn_once(
            f"{label} is not a clean absolute path; refusing relative/CWD "
            "fallback (D28); playing without persistence (session-best TOP)"
        )
        return None
    # Canonicalize and re-verify: the app dir must stay a direct child of the
    # resolved base (CWE-23 guard; D24 no-user-supplied-paths).
    base_real = os.path.realpath(base_raw)
    target_real = os.path.realpath(os.path.join(base_real, _APP_DIR_NAME))
    if not target_real.startswith(base_real + os.sep):
        _warn_once(
            f"{label} resolves outside itself; refusing (D24/D28); "
            "playing without persistence (session-best TOP)"
        )
        return None
    target = Path(target_real)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        _warn_once(
            f"cannot create data directory under {label}; "
            "playing without persistence (session-best TOP)"
        )
        return None
    return target


def data_dir(env: Mapping[str, str] | None = None) -> Path | None:
    """Resolve and create the per-user Kenjiri data directory.

    On Windows this is ``%LOCALAPPDATA%\\Kenjiri``; on macOS it is
    ``~/Library/Application Support/Kenjiri``. An injected ``env`` mapping
    containing ``LOCALAPPDATA`` always selects the Windows resolver (so the
    suite can exercise it from any host); otherwise, on macOS, ``HOME`` is
    read from the same mapping. Both paths share the D24/D28 guards.

    Args:
        env: Environment mapping to resolve from; defaults to ``os.environ``
            (injectable for tests so the real user directory is never touched).

    Returns:
        The absolute Kenjiri data directory (created if needed), or ``None``
        when the base is missing/empty/relative or the directory cannot be
        created (D28).
    """
    source: Mapping[str, str] = os.environ if env is None else env
    if "LOCALAPPDATA" in source or sys.platform != "darwin":
        return _app_dir(source.get("LOCALAPPDATA", ""), "LOCALAPPDATA")
    home = source.get("HOME", "")
    base = os.path.join(home, "Library", "Application Support") if home else ""
    return _app_dir(base, "~/Library/Application Support")


def db_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the high-score database path, or ``None`` when unresolvable.

    Args:
        env: Optional environment mapping override (testability injection).

    Returns:
        ``<data_dir>/kenjiri.db`` or ``None`` per :func:`data_dir`.
    """
    base = data_dir(env)
    return None if base is None else base / _DB_FILENAME


def log_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the application log path, or ``None`` when unresolvable.

    Args:
        env: Optional environment mapping override (testability injection).

    Returns:
        ``<data_dir>/kenjiri.log`` or ``None`` per :func:`data_dir`.
    """
    base = data_dir(env)
    return None if base is None else base / _LOG_FILENAME
