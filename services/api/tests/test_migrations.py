"""Миграции Alembic совпадают с моделями и обратимы — на SQLite и на PostgreSQL."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

import app.db.models  # noqa: F401
from app.db.base import Base

API_DIR = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"


def _postgres_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param("postgres", marks=pytest.mark.postgres),
    ]
)
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    if request.param == "sqlite":
        yield _sqlite_url(tmp_path)
        return
    url = _postgres_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL не задан")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    engine.dispose()
    yield url


def _diff(engine: Engine) -> list[object]:
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        return list(compare_metadata(context, Base.metadata))


def test_upgrade_matches_models_and_downgrade_is_clean(database_url: str) -> None:
    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        assert _diff(engine) == [], "миграции разошлись с моделями — нужна новая ревизия"
        tables = set(inspect(engine).get_table_names())
        assert set(Base.metadata.tables) <= tables

        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()
