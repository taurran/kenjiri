"""Tests for kenjiri.persistence (T4): paths, applog, highscore.

All filesystem activity is confined to pytest tmp_path via injected env
dicts — the real %LOCALAPPDATA% is never touched (PLAN T4 acceptance).
"""
from __future__ import annotations

import ast
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kenjiri.persistence import applog, paths  # noqa: E402
from kenjiri.persistence.highscore import HighScoreStore  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_logging_and_warn_flag(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reset the log-once flag and detach/close kenjiri log handlers per test."""
    monkeypatch.setattr(paths, "_warned_unresolvable", False)
    yield
    logger = logging.getLogger("kenjiri")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def _env(tmp_path: Path) -> dict[str, str]:
    """Injected env dict pointing LOCALAPPDATA at tmp_path."""
    return {"LOCALAPPDATA": str(tmp_path)}


# ---------------------------------------------------------------- paths


def test_data_dir_creates_and_returns_dir(tmp_path: Path) -> None:
    result = paths.data_dir(_env(tmp_path))
    assert result == tmp_path / "Kenjiri"
    assert result.is_dir()


def test_db_and_log_paths_under_data_dir(tmp_path: Path) -> None:
    assert paths.db_path(_env(tmp_path)) == tmp_path / "Kenjiri" / "kenjiri.db"
    assert paths.log_path(_env(tmp_path)) == tmp_path / "Kenjiri" / "kenjiri.log"


def test_missing_localappdata_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "cwd"
    sandbox.mkdir()
    monkeypatch.chdir(sandbox)
    assert paths.data_dir({}) is None
    assert paths.db_path({}) is None
    assert paths.log_path({}) is None
    assert paths.data_dir({"LOCALAPPDATA": ""}) is None
    # D28 negative: never fall back to a relative/CWD path.
    assert list(sandbox.iterdir()) == []


def test_relative_localappdata_never_falls_back_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "cwd"
    sandbox.mkdir()
    monkeypatch.chdir(sandbox)
    assert paths.data_dir({"LOCALAPPDATA": "relative\\appdata"}) is None
    assert paths.data_dir({"LOCALAPPDATA": "."}) is None
    assert list(sandbox.iterdir()) == []


def test_unwritable_base_returns_none(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file, not directory", encoding="utf-8")
    assert paths.data_dir({"LOCALAPPDATA": str(blocker)}) is None


def test_unresolvable_logs_once(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="kenjiri"):
        paths.data_dir({})
        paths.data_dir({})
        paths.db_path({})
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


# ---------------------------------------------------------------- applog


def test_get_logger_writes_to_file(tmp_path: Path) -> None:
    logger = applog.get_logger(_env(tmp_path))
    logger.info("hello kenjiri")
    log_file = tmp_path / "Kenjiri" / "kenjiri.log"
    assert log_file.is_file()
    assert "hello kenjiri" in log_file.read_text(encoding="utf-8")


def test_log_truncated_above_1mb(tmp_path: Path) -> None:
    log_file = tmp_path / "Kenjiri" / "kenjiri.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b"x" * (1_048_576 + 512))
    applog.get_logger(_env(tmp_path))
    assert log_file.stat().st_size < 1_048_576


def test_small_log_not_truncated(tmp_path: Path) -> None:
    log_file = tmp_path / "Kenjiri" / "kenjiri.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text("keep me\n", encoding="utf-8")
    logger = applog.get_logger(_env(tmp_path))
    logger.info("appended")
    content = log_file.read_text(encoding="utf-8")
    assert "keep me" in content
    assert "appended" in content


def test_get_logger_unavailable_disables_silently() -> None:
    logger = applog.get_logger({})
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
    logger.info("must not raise")  # D28: degraded modes never crash


def test_get_logger_idempotent_single_file_handler(tmp_path: Path) -> None:
    applog.get_logger(_env(tmp_path))
    logger = applog.get_logger(_env(tmp_path))
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1


# ---------------------------------------------------------------- highscore


def _store(tmp_path: Path) -> HighScoreStore:
    return HighScoreStore(tmp_path / "kenjiri.db")


def test_round_trip_persist_and_reopen(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.top() == 0
    assert store.submit(1200, lines=4, level=0) is True
    assert store.top() == 1200
    store.close()
    reopened = _store(tmp_path)
    assert reopened.top() == 1200
    reopened.close()


def test_submit_lower_or_equal_returns_false_and_preserves(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.submit(3600, lines=12, level=2) is True
    assert store.submit(1200, lines=4, level=0) is False
    assert store.submit(3600, lines=13, level=3) is False
    store.close()
    reopened = _store(tmp_path)
    assert reopened.top() == 3600
    reopened.close()


def test_corrupt_db_recreates_and_functions(tmp_path: Path) -> None:
    db = tmp_path / "kenjiri.db"
    db.write_bytes(b"this is definitely not a sqlite database file at all")
    store = HighScoreStore(db)
    assert store.top() == 0
    assert store.submit(500, lines=2, level=0) is True
    store.close()
    reopened = HighScoreStore(db)
    assert reopened.top() == 500
    reopened.close()


def test_schema_version_mismatch_recreates(tmp_path: Path) -> None:
    db = tmp_path / "kenjiri.db"
    conn = sqlite3.connect(db)
    with conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (999,))
    conn.close()
    store = HighScoreStore(db)
    assert store.top() == 0
    assert store.submit(40, lines=1, level=0) is True
    store.close()


def test_db_path_none_session_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "cwd"
    sandbox.mkdir()
    monkeypatch.chdir(sandbox)
    store = HighScoreStore(None)
    assert store.top() == 0
    # Nothing is persisted in session-only mode, so submit reports False (D21/D24)
    assert store.submit(700, lines=3, level=1) is False
    assert store.top() == 700  # session-best TOP (D24/D28)
    assert store.submit(300, lines=1, level=0) is False
    assert store.top() == 700
    store.close()
    assert list(sandbox.iterdir()) == []  # never writes a CWD/relative file


class _ExplodingConn:
    """Proxy that lets the highscore UPSERT execute, then fails before commit."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real

    def __enter__(self) -> sqlite3.Connection:
        return self._real.__enter__()

    def __exit__(self, *exc_info: Any) -> bool:
        return bool(self._real.__exit__(*exc_info))

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self._real.execute(sql, params)
        if "INSERT INTO highscore" in sql:
            raise sqlite3.OperationalError("simulated failure after write, before commit")
        return cursor

    def close(self) -> None:
        self._real.close()


def test_mid_submit_failure_leaves_prior_record_intact(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.submit(1000, lines=5, level=1) is True
    store._conn = _ExplodingConn(store._conn)  # type: ignore[assignment]
    assert store.submit(2000, lines=10, level=2) is False  # rolled back, degraded
    assert store.top() == 2000  # session-best still shown per D24
    store.close()
    reopened = _store(tmp_path)
    assert reopened.top() == 1000  # prior record intact — transaction atomicity (D24)
    reopened.close()


def test_no_sql_string_interpolation_static_scan() -> None:
    """Parameterized-queries-only proof (D24): no f-string/%-format/.format/concat
    whose string content contains SELECT/INSERT/UPDATE/DELETE in highscore.py."""
    source_path = _SRC / "kenjiri" / "persistence" / "highscore.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    keywords = ("SELECT", "INSERT", "UPDATE", "DELETE")

    def has_sql(text: str) -> bool:
        upper = text.upper()
        return any(k in upper for k in keywords)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if (
                    isinstance(part, ast.Constant)
                    and isinstance(part.value, str)
                    and has_sql(part.value)
                ):
                    offenders.append(f"f-string with SQL at line {node.lineno}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            for side in (node.left, node.right):
                if (
                    isinstance(side, ast.Constant)
                    and isinstance(side.value, str)
                    and has_sql(side.value)
                ):
                    op_name = type(node.op).__name__
                    offenders.append(f"string {op_name} with SQL at line {node.lineno}")
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "format"
                and isinstance(func.value, ast.Constant)
                and isinstance(func.value.value, str)
                and has_sql(func.value.value)
            ):
                offenders.append(f".format() with SQL at line {node.lineno}")
    assert offenders == [], f"SQL built via interpolation: {offenders}"
