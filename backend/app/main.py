"""Wind Procurement Desk -- API entrypoint.

Serves the day-ahead decision view and the forecast-accuracy analytics that sit
behind it, over a pre-ingested snapshot of Elexon BMRS data for January 2026.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS, DB_PATH
from app.core.db import init_db
from app.routers import accuracy, decision

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The shipped snapshot already has its schema; only create one when the
    # database is genuinely absent, so a read-only host is never written to.
    if DB_PATH.exists():
        logging.info("Serving snapshot %s", DB_PATH)
    else:
        logging.warning("Database %s is missing; run python -m app.services.ingest", DB_PATH)
        init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Wind Procurement Desk API",
    description=(
        "Day-ahead wind forecast and forecast-accuracy analytics for a UK "
        "utility's power procurement desk. Data: Elexon BMRS FUELHH + WINDFOR."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(decision.router)
app.include_router(accuracy.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "database": DB_PATH.name, "present": DB_PATH.exists()}
