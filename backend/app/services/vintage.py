"""Forecast vintage selection -- the correctness heart of the product.

A buyer acting on delivery day D places their bid before the day-ahead auction
closes at 11:00 UK time on D-1. Any WINDFOR publication timestamped after that
instant is hindsight. Every number this application shows as a "decision-time"
forecast is therefore drawn from the newest vintage at or before gate closure,
and never from a later restatement.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import GATE_CLOSURE_LOCAL, UK_TZ

_UK = ZoneInfo(UK_TZ)


def gate_closure_for(delivery_day: date) -> datetime:
    """UTC instant at which bidding for `delivery_day` closes.

    Expressed in UK local time first so the rule stays correct across the BST
    boundary, even though the January scope of this build never crosses it.
    """
    local = datetime.combine(delivery_day - timedelta(days=1), GATE_CLOSURE_LOCAL, tzinfo=_UK)
    return local.astimezone(timezone.utc)


def delivery_window(delivery_day: date) -> tuple[datetime, datetime]:
    """[start, end) UTC bounds of a UK local delivery day."""
    start = datetime.combine(delivery_day, datetime.min.time(), tzinfo=_UK)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def as_of_forecast(conn, delivery_day: date, as_of: datetime | None = None) -> list[dict]:
    """Latest forecast for each hour of `delivery_day` known at `as_of`.

    Defaults to gate closure. Implemented as a correlated max(publish_time) so
    that a target hour revised by a later vintage still resolves to the single
    most recent value that existed at the cut-off.
    """
    cutoff = as_of or gate_closure_for(delivery_day)
    win_start, win_end = delivery_window(delivery_day)

    rows = conn.execute(
        """
        SELECT f.start_time, f.generation, f.publish_time
        FROM forecasts f
        JOIN (
            SELECT start_time, MAX(publish_time) AS publish_time
            FROM forecasts
            WHERE publish_time <= :cutoff
              AND start_time >= :win_start
              AND start_time <  :win_end
            GROUP BY start_time
        ) latest
          ON latest.start_time = f.start_time
         AND latest.publish_time = f.publish_time
        ORDER BY f.start_time
        """,
        {
            "cutoff": _iso(cutoff),
            "win_start": _iso(win_start),
            "win_end": _iso(win_end),
        },
    ).fetchall()

    return [
        {
            "start_time": r["start_time"],
            "generation": r["generation"],
            "publish_time": r["publish_time"],
            "horizon_hours": _hours_between(r["publish_time"], r["start_time"]),
        }
        for r in rows
    ]


def available_vintages(conn, delivery_day: date) -> list[str]:
    """Every publication that says something about `delivery_day`, oldest first."""
    win_start, win_end = delivery_window(delivery_day)
    rows = conn.execute(
        """
        SELECT DISTINCT publish_time FROM forecasts
        WHERE start_time >= ? AND start_time < ?
        ORDER BY publish_time
        """,
        (_iso(win_start), _iso(win_end)),
    ).fetchall()
    return [r["publish_time"] for r in rows]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _hours_between(publish_time: str, start_time: str) -> float:
    return round((_parse(start_time) - _parse(publish_time)).total_seconds() / 3600.0, 2)
