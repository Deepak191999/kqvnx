"""Accuracy endpoints: how much the buyer should distrust the forecast."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import analysis, calibration
from app.services.cache import cached_horizon_frame, cached_month_frame

router = APIRouter(prefix="/api/accuracy", tags=["accuracy"])


@router.get("/summary")
def summary() -> dict:
    """Headline error metrics over every January decision, plus the risk read.

    All statistics are computed on gate-closure vintages only, so they describe
    the accuracy the desk actually faces -- not the accuracy of a forecast
    refreshed after the auction had already closed.
    """
    month = cached_month_frame()
    if month.empty:
        raise HTTPException(503, "No paired data available; run the ingest job.")

    stats = analysis.error_stats(month)
    over_rate = float((month["error"] > 0).mean() * 100)

    return {
        "scope": {
            "delivery_days": int(month["delivery_date"].nunique()),
            "delivery_hours": int(len(month)),
            "basis": "latest WINDFOR vintage published at or before 11:00 UK on D-1",
        },
        "metrics": stats,
        "risk": {
            "over_forecast_rate_pct": round(over_rate, 1),
            # The 80% central interval is the practical hedging range: on four
            # days in five the shortfall lands inside these bounds.
            "p10_error_mw": stats["p10"],
            "p90_error_mw": stats["p90"],
            "interpretation": (
                "error = forecast - actual; a positive value means wind "
                "under-delivered and the desk was short at delivery."
            ),
        },
        "calibration": calibration.comparison(month),
    }


@router.get("/by-day")
def by_day() -> list[dict]:
    return analysis.stats_by(cached_month_frame(), "delivery_date")


@router.get("/by-hour")
def by_hour() -> list[dict]:
    """Time-of-day error profile -- reveals systematic intraday patterns."""
    return analysis.stats_by(cached_month_frame(), "hour_of_day")


@router.get("/by-horizon")
def by_horizon() -> dict:
    """Error against lead time, across every vintage rather than just the one used.

    Shows what the D-1 11:00 cut-off costs: the desk is forced to commit at a
    14-38 hour lead time, well before the forecast reaches its best skill.
    """
    horizon = cached_horizon_frame()
    if horizon.empty:
        raise HTTPException(503, "No paired data available; run the ingest job.")

    month = cached_month_frame()
    return {
        "buckets": analysis.stats_by_horizon(horizon),
        "gate_closure_horizon_hours": {
            "min": float(month["horizon_hours"].min()),
            "max": float(month["horizon_hours"].max()),
        },
    }


@router.get("/distribution")
def distribution() -> dict:
    """Histogram of gate-closure error, the basis of the P10/P90 band."""
    month = cached_month_frame()
    return {
        "bins": analysis.error_histogram(month),
        "metrics": analysis.error_stats(month),
    }


@router.get("/series")
def series() -> list[dict]:
    """Full paired time series for the overlay chart."""
    month = cached_month_frame()
    if month.empty:
        return []
    cols = ["start_time", "delivery_date", "forecast", "actual", "error", "horizon_hours"]
    return month[cols].to_dict(orient="records")
