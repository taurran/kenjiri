"""Degraded-mode-safe file logging for Kenjiri (D28).

With ``--noconsole`` there is no stdout/stderr, so the file at
``%LOCALAPPDATA%\\Kenjiri\\kenjiri.log`` is the only sink. The log is opened
in append mode and truncated when it exceeds 1 MB. If the log path itself is
unavailable, logging disables silently (NullHandler) — degraded modes must
never crash the game they're protecting (D28).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

from kenjiri.persistence import paths

_MAX_LOG_BYTES = 1_048_576  # 1 MB (D28: "truncate above 1 MB")
_LOGGER_NAME = "kenjiri"
_MANAGED_ATTR = "_kenjiri_managed"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _remove_managed_handlers(logger: logging.Logger) -> None:
    """Detach and close handlers previously attached by :func:`get_logger`."""
    for handler in list(logger.handlers):
        if getattr(handler, _MANAGED_ATTR, False):
            logger.removeHandler(handler)
            handler.close()


def _truncate_if_oversized(target: Path) -> None:
    """Truncate the log file when it exceeds the 1 MB cap (D28)."""
    if target.exists() and target.stat().st_size > _MAX_LOG_BYTES:
        with open(target, "w", encoding="utf-8"):
            pass


def get_logger(env: Mapping[str, str] | None = None) -> logging.Logger:
    """Return the ``kenjiri`` logger configured per D28.

    Attaches a file handler at ``%LOCALAPPDATA%\\Kenjiri\\kenjiri.log``
    (append mode, truncated first when above 1 MB). When the log path is
    unresolvable or unwritable, only a NullHandler is attached and logging
    disables silently — this function never raises.

    Args:
        env: Optional environment mapping override passed through to
            :func:`kenjiri.persistence.paths.log_path` (testability injection).

    Returns:
        The configured ``kenjiri`` logger. Repeated calls reconfigure in
        place without duplicating handlers.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    _remove_managed_handlers(logger)
    null_handler = logging.NullHandler()
    setattr(null_handler, _MANAGED_ATTR, True)
    logger.addHandler(null_handler)
    try:
        target = paths.log_path(env)
        if target is None:
            return logger
        _truncate_if_oversized(target)
        file_handler = logging.FileHandler(target, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        setattr(file_handler, _MANAGED_ATTR, True)
        logger.addHandler(file_handler)
    except OSError:
        pass  # D28: log path unavailable — logging disables silently
    return logger
