"""SQLite storage. Small, file-backed and committed to the image so that the
deployed demo never depends on Elexon being reachable at request time."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app.core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS actuals (
    start_time        TEXT PRIMARY KEY,
    settlement_date   TEXT NOT NULL,
    settlement_period INTEGER NOT NULL,
    generation        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_actuals_date ON actuals (settlement_date);

CREATE TABLE IF NOT EXISTS forecasts (
    publish_time TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    generation   REAL NOT NULL,
    PRIMARY KEY (publish_time, start_time)
);
CREATE INDEX IF NOT EXISTS ix_forecasts_start ON forecasts (start_time);
CREATE INDEX IF NOT EXISTS ix_forecasts_pub   ON forecasts (publish_time);

CREATE TABLE IF NOT EXISTS ingest_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    # Resolved through the module rather than imported by value so that tests
    # can repoint DB_PATH at a temporary fixture database.
    db_path = config.DB_PATH

    # Serverless platforms mount the deployment bundle read-only. Opening the
    # snapshot in SQLite's read-only URI mode avoids the journal file that a
    # normal open would try to create next to it.
    if config.READ_ONLY_DB and db_path.exists():
        conn = sqlite3.connect(
            f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False
        )
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)

    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)
