"""One-shot ingest: pull the January 2026 window from Elexon into SQLite.

Run with:  python -m app.services.ingest
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.config import (
    ACTUALS_DATE_FROM,
    ACTUALS_DATE_TO,
    FORECAST_PUBLISH_FROM,
    FORECAST_PUBLISH_TO,
    RAW_DIR,
)
from app.core.db import init_db, session
from app.services.elexon_client import fetch_actuals, fetch_forecasts

log = logging.getLogger(__name__)


def _norm(ts: str) -> str:
    """Normalise Elexon timestamps to a sortable UTC ISO string.

    Lexicographic ordering of this format matches chronological ordering, which
    is what lets the vintage queries use plain SQL comparisons on TEXT columns.
    """
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def store_actuals(rows: list[dict]) -> int:
    clean = {}
    for r in rows:
        if r.get("fuelType") != "WIND" or r.get("generation") is None:
            continue
        st = _norm(r["startTime"])
        # Elexon can restate a settlement period; the later publication wins.
        clean[st] = (st, r["settlementDate"], r["settlementPeriod"], float(r["generation"]))
    with session() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO actuals VALUES (?,?,?,?)", list(clean.values())
        )
    return len(clean)


def store_forecasts(rows: list[dict]) -> int:
    clean = {}
    for r in rows:
        if r.get("generation") is None:
            continue
        key = (_norm(r["publishTime"]), _norm(r["startTime"]))
        clean[key] = (key[0], key[1], float(r["generation"]))
    with session() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO forecasts VALUES (?,?,?)", list(clean.values())
        )
    return len(clean)


def run() -> dict:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Fetching WIND actuals %s..%s", ACTUALS_DATE_FROM, ACTUALS_DATE_TO)
    actuals = fetch_actuals(ACTUALS_DATE_FROM, ACTUALS_DATE_TO)
    (RAW_DIR / "fuelhh_wind.json").write_text(json.dumps(actuals))
    n_act = store_actuals(actuals)

    log.info("Fetching WINDFOR vintages %s..%s", FORECAST_PUBLISH_FROM, FORECAST_PUBLISH_TO)
    forecasts = fetch_forecasts(FORECAST_PUBLISH_FROM, FORECAST_PUBLISH_TO)
    (RAW_DIR / "windfor.json").write_text(json.dumps(forecasts))
    n_fc = store_forecasts(forecasts)

    with session() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ingest_meta VALUES ('ingested_at', ?)",
            (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),),
        )
    summary = {"actual_rows": n_act, "forecast_rows": n_fc}
    log.info("Ingest complete: %s", summary)
    return summary


if __name__ == "__main__":
    run()
