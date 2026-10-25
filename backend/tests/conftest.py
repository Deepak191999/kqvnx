"""Fixtures backed by a small, hand-built database.

Tests run against synthetic data with known answers rather than the ingested
January snapshot, so a failure points at the logic and not at Elexon.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core import config
from app.core.db import SCHEMA, connect
from app.services import cache


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Empty database at a temporary path, wired into the app config."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    cache.reset()
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    yield conn
    conn.close()
    cache.reset()


@pytest.fixture
def seeded(db):
    """One delivery day (2026-01-10) with three forecast vintages.

    The 09:30 vintage is the last before the 11:00 D-1 gate closure; the 13:30
    vintage is published after it and must never be selected. Each vintage
    reports a distinct, easily recognisable generation level.
    """
    day = datetime(2026, 1, 10, tzinfo=timezone.utc)

    forecasts = []
    for pub_hour, level in ((2.5, 1000.0), (9.5, 2000.0), (13.5, 3000.0)):
        pub = datetime(2026, 1, 9, tzinfo=timezone.utc) + timedelta(hours=pub_hour)
        for h in range(24):
            forecasts.append((_iso(pub), _iso(day + timedelta(hours=h)), level))

    # Actuals: a flat 1500 MW, delivered as two equal half-hourly periods.
    actuals = []
    for h in range(24):
        for half in (0, 30):
            ts = day + timedelta(hours=h, minutes=half)
            actuals.append((_iso(ts), "2026-01-10", h * 2 + (1 if half == 0 else 2), 1500.0))

    db.executemany("INSERT INTO forecasts VALUES (?,?,?)", forecasts)
    db.executemany("INSERT INTO actuals VALUES (?,?,?,?)", actuals)
    db.commit()
    cache.reset()
    return db
