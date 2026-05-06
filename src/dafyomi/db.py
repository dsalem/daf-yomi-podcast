"""SQLAlchemy engine + session factory + schema bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def db_url() -> str:
    return os.environ.get("DAFYOMI_DB", "sqlite:///./dafyomi.db")


def make_engine(url: str | None = None) -> Engine:
    eng = create_engine(url or db_url(), future=True)
    if eng.url.get_backend_name() == "sqlite":
        # Foreign keys are off by default in SQLite.
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.close()
    return eng


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_schema(engine: Engine) -> None:
    """Create all tables. Idempotent — safe to call repeatedly."""
    Base.metadata.create_all(engine)
    _additive_migrations(engine)
    _seed_seasons(engine)


def _additive_migrations(engine: Engine) -> None:
    """Apply additive ALTER TABLE migrations for column additions.

    SQLite ≥3.35 and Postgres ≥9.6 both support `ADD COLUMN IF NOT EXISTS`,
    but SQLite still raises if the column exists when used without — so we
    introspect first.
    """
    backend = engine.url.get_backend_name()
    if backend == "sqlite":
        with engine.begin() as conn:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(episodes)"))}
            if "amud" not in cols:
                conn.execute(text("ALTER TABLE episodes ADD COLUMN amud VARCHAR(1)"))
            if "daf_end" not in cols:
                conn.execute(text("ALTER TABLE episodes ADD COLUMN daf_end INTEGER"))
            if "amud_end" not in cols:
                conn.execute(text("ALTER TABLE episodes ADD COLUMN amud_end VARCHAR(1)"))
    else:
        # Postgres path (forward-compatible).
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS amud VARCHAR(1)"))
            conn.execute(text("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS daf_end INTEGER"))
            conn.execute(text("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS amud_end VARCHAR(1)"))


def _seed_seasons(engine: Engine) -> None:
    """Pre-populate the seasons table from the canonical Bavli order."""
    from .seasons import MASECHTOT

    with engine.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(text("SELECT masechet_slug FROM seasons"))
        }
        for m in MASECHTOT:
            if m.slug in existing:
                continue
            conn.execute(
                text(
                    "INSERT INTO seasons "
                    "(masechet_slug, masechet_name_en, masechet_name_he, season_number) "
                    "VALUES (:slug, :en, :he, :n)"
                ),
                {"slug": m.slug, "en": m.name_en, "he": m.name_he, "n": m.season_number},
            )


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
