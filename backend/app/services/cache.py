"""Process-level memoisation of the expensive frames.

The month frame replays 31 delivery days through the vintage query, and the
horizon frame joins ~20k forecast rows to outturn. Both are derived from a
read-only snapshot of the database, so they are computed once per process and
reused. `reset()` exists so tests can force a rebuild after seeding fixtures.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from app.core.db import connect
from app.services import analysis


@lru_cache(maxsize=1)
def _month() -> pd.DataFrame:
    conn = connect()
    try:
        return analysis.month_frame(conn)
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _horizon() -> pd.DataFrame:
    conn = connect()
    try:
        return analysis.all_horizon_frame(conn)
    finally:
        conn.close()


def cached_month_frame() -> pd.DataFrame:
    """Gate-closure forecast vs outturn for every delivery day in scope."""
    return _month().copy()


def cached_horizon_frame() -> pd.DataFrame:
    """Every (vintage, target hour) pair with its lead time and error."""
    return _horizon().copy()


def reset() -> None:
    _month.cache_clear()
    _horizon.cache_clear()
