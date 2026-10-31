"""SQLite-настройки демо-стенда допускают параллельное чтение и ждут писателя."""

from pathlib import Path

from sqlalchemy import text

from app.db.session import make_engine


def test_file_sqlite_uses_wal_and_busy_timeout(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'stand.db'}")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
            assert connection.scalar(text("PRAGMA busy_timeout")) == 30_000
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()
