import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

settings = get_settings()

# SQLite can create the database FILE but not a missing parent directory - if DATABASE_URL points
# inside a not-yet-created path (e.g. a fresh persistent-disk mount before anything else has
# written to it), connecting fails with "unable to open database file". Ensure the directory
# exists first so this doesn't depend on some other code path having created it as a side effect.
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


# Columns added after a database may already exist (create_all never alters existing tables and this
# project has no migration tool). Each entry: (table, column, SQL type + default).
_ADDED_COLUMNS = [
    ("turns", "retrieved_chunks", "JSON"),
    ("turns", "config_version", "INTEGER"),
    ("documents", "source_text", "TEXT"),
    ("documents", "source_reconstructed", "BOOLEAN DEFAULT 0"),
]


def _add_missing_columns() -> None:
    """Idempotently ALTER TABLE ... ADD COLUMN for anything in _ADDED_COLUMNS that's missing, before
    anything queries it. All additions are nullable/defaulted so existing rows stay valid."""
    insp = inspect(engine)
    for table, column, ddl in _ADDED_COLUMNS:
        existing = {c["name"] for c in insp.get_columns(table)}
        if column not in existing:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
