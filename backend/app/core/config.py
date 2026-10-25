"""Central configuration and domain constants.

The whole product is pinned to a single business question -- "what should we buy
on the UK day-ahead market for delivery day D?" -- so the knobs that encode that
question live here rather than being scattered through the services.
"""
from __future__ import annotations

import os
from datetime import date, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "wind.db"))

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

# --- Domain constants -------------------------------------------------------

# The N2EX/EPEX UK day-ahead auction closes at 11:00 UK local time on D-1. Every
# forecast published after this instant is information the buyer did NOT have
# when the purchase decision was made, so it must never enter the decision view.
GATE_CLOSURE_LOCAL = time(11, 0)
UK_TZ = "Europe/London"

# The brief scopes us to purchase decisions taken in January 2026. A decision on
# D-1 buys power for delivery on D, so the delivery window runs one day later.
DECISION_DATE_FROM = date(2026, 1, 1)
DECISION_DATE_TO = date(2026, 1, 31)
DELIVERY_DATE_FROM = date(2026, 1, 2)
DELIVERY_DATE_TO = date(2026, 2, 1)

# Elexon publishes WINDFOR hourly and FUELHH half-hourly. We reconcile on the
# coarser hourly grid so that no value is ever invented by interpolation.
COMPARISON_FREQ = "h"

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

# A vintage can look up to ~3 days ahead, so to study how error decays with
# horizon we need publications from a few days before the first delivery day.
FORECAST_PUBLISH_FROM = date(2025, 12, 29)
FORECAST_PUBLISH_TO = date(2026, 2, 1)

# Actuals only need to span the delivery window itself.
ACTUALS_DATE_FROM = date(2026, 1, 1)
ACTUALS_DATE_TO = date(2026, 2, 1)

# Set on read-only hosts (Vercel and other serverless bundles) so the snapshot
# is opened without SQLite attempting to create a journal beside it.
READ_ONLY_DB = os.getenv("READ_ONLY_DB", "").lower() in {"1", "true", "yes"}
