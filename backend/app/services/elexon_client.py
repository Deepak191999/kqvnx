"""Thin client over the Elexon BMRS Insights streaming endpoints.

Only two datasets are in scope:
  FUELHH  -- half-hourly metered generation by fuel type (we keep fuelType=WIND)
  WINDFOR -- hourly national wind generation forecast, republished ~5x per day
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from app.core.config import ELEXON_BASE_URL

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0, connect=30.0)
_CHUNK_DAYS = 7


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _windows(start: date, end: date, step_days: int = _CHUNK_DAYS):
    """Yield (from, to) UTC datetime pairs covering [start, end] inclusive."""
    cursor = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    final = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
    while cursor < final:
        nxt = min(cursor + timedelta(days=step_days), final)
        yield cursor, nxt
        cursor = nxt


def _get(client: httpx.Client, path: str, params: dict) -> list[dict]:
    resp = client.get(f"{ELEXON_BASE_URL}{path}", params=params)
    resp.raise_for_status()
    payload = resp.json()
    # The stream endpoints return a bare array; the paged ones wrap it in "data".
    return payload if isinstance(payload, list) else payload.get("data", [])


def fetch_actuals(start: date, end: date) -> list[dict]:
    """Half-hourly WIND actuals with settlement dates in [start, end]."""
    rows: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for frm, to in _windows(start, end):
            # FUELHH publishes a period ~30 min after it starts, so we widen the
            # publish window by a day on each side and filter precisely later.
            batch = _get(
                client,
                "/datasets/FUELHH/stream",
                {
                    "publishDateTimeFrom": _iso(frm - timedelta(days=1)),
                    "publishDateTimeTo": _iso(to + timedelta(days=1)),
                    "fuelType": "WIND",
                },
            )
            log.info("FUELHH %s..%s -> %d rows", _iso(frm), _iso(to), len(batch))
            rows.extend(batch)
    return rows


def fetch_forecasts(start: date, end: date) -> list[dict]:
    """Every WINDFOR vintage published in [start, end]."""
    rows: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for frm, to in _windows(start, end):
            batch = _get(
                client,
                "/datasets/WINDFOR/stream",
                {"publishDateTimeFrom": _iso(frm), "publishDateTimeTo": _iso(to)},
            )
            log.info("WINDFOR %s..%s -> %d rows", _iso(frm), _iso(to), len(batch))
            rows.extend(batch)
    return rows
