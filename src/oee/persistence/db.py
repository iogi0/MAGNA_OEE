"""Engine a session pre SQLite (ARCHITECTURE §10.2).

- `PRAGMA foreign_keys=ON` pri každom pripojení (SQLite má FK predvolene vypnuté);
- `check_same_thread=False` + `busy_timeout` (FastAPI a background úlohy bežia v iných vláknach);
- súborová DB: WAL a vytvorenie priečinka; testy: `make_engine(None)` = zdieľaná in-memory DB (`StaticPool`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, StaticPool, create_engine, event
from sqlalchemy.orm import sessionmaker

from oee.persistence.models import Base

BUSY_TIMEOUT_MS = 5000


def _set_pragmas(file_db: bool) -> Any:
    def on_connect(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            if file_db:
                cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return on_connect


def make_engine(db_path: Path | None) -> Engine:
    """Engine pre súbor `db_path`, alebo zdieľanú in-memory DB pri `None` (testy)."""
    connect_args = {"check_same_thread": False}
    if db_path is None:
        engine = create_engine("sqlite://", connect_args=connect_args, poolclass=StaticPool)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args=connect_args)
    event.listen(engine, "connect", _set_pragmas(file_db=db_path is not None))
    return engine


def make_session_factory(engine: Engine) -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Vytvorí chýbajúce tabuľky (MVP bez migrácií; Alembic je P2)."""
    Base.metadata.create_all(engine)
