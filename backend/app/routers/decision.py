"""Decision-support endpoints: what the buyer sees before the auction closes."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.config import DELIVERY_DATE_FROM, DELIVERY_DATE_TO
from app.core.db import connect
from app.services import analysis, calibration
from app.services.vintage import (
    as_of_forecast,
    available_vintages,
    delivery_window,
    gate_closure_for,
)
from app.services.cache import cached_month_frame

router = APIRouter(prefix="/api", tags=["decision"])


def _check_range(d: date) -> None:
    if not (DELIVERY_DATE_FROM <= d <= DELIVERY_DATE_TO):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Delivery day {d} is outside the ingested window "
                f"({DELIVERY_DATE_FROM}..{DELIVERY_DATE_TO})."
            ),
        )


@router.get("/meta")
def meta() -> dict:
    """Window, conventions and data counts -- lets the UI configure itself."""
    conn = connect()
    try:
        n_act = conn.execute("SELECT COUNT(*) c FROM actuals").fetchone()["c"]
        n_fc = conn.execute("SELECT COUNT(*) c FROM forecasts").fetchone()["c"]
        row = conn.execute(
            "SELECT value FROM ingest_meta WHERE key='ingested_at'"
        ).fetchone()
    finally:
        conn.close()

    return {
        "delivery_date_from": DELIVERY_DATE_FROM.isoformat(),
        "delivery_date_to": DELIVERY_DATE_TO.isoformat(),
        "gate_closure_local": "11:00 Europe/London on D-1",
        "actual_rows": n_act,
        "forecast_rows": n_fc,
        "ingested_at": row["value"] if row else None,
        "sources": {
            "actuals": "Elexon BMRS FUELHH (fuelType=WIND, half-hourly)",
            "forecast": "Elexon BMRS WINDFOR (hourly, ~5 vintages per day)",
        },
    }


@router.get("/decision/{delivery_date}")
def decision_view(
    delivery_date: date,
    calibrated: bool = Query(True, description="Apply the walk-forward bias correction"),
) -> dict:
    """The forecast curve as it stood at gate closure, with a risk band.

    Everything returned here was knowable before the auction closed on D-1:
    the forecast vintage is filtered to that cut-off, and the calibration is
    fitted only on delivery days that had already settled.
    """
    _check_range(delivery_date)
    conn = connect()
    try:
        gate = gate_closure_for(delivery_date)
        raw = as_of_forecast(conn, delivery_date)
        if not raw:
            raise HTTPException(404, f"No forecast vintage found before gate closure for {delivery_date}.")

        month = cached_month_frame()
        # Only history strictly before this delivery day may shape the band.
        history = month[month["delivery_date"] < delivery_date.isoformat()]
        params = calibration.fit(history) if not history.empty else None

        points = analysis.uncertainty_band(history, raw)
        for p in points:
            p["calibrated"] = calibration.apply(p["generation"], params) if calibrated else None

        # Outturn is shown only for days already delivered -- it is review
        # material, never an input to the decision itself.
        actual_map = {
            r["start_time"]: r["actual"]
            for _, r in analysis.decision_frame(conn, delivery_date).iterrows()
        }
        for p in points:
            p["actual"] = actual_map.get(p["start_time"])

        total_raw = sum(p["generation"] for p in points)
        total_cal = sum(p["calibrated"] or p["generation"] for p in points)

        return {
            "delivery_date": delivery_date.isoformat(),
            "gate_closure_utc": gate.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vintage_used": points[0]["publish_time"],
            "vintages_available_total": len(available_vintages(conn, delivery_date)),
            "horizon_hours": {
                "min": min(p["horizon_hours"] for p in points),
                "max": max(p["horizon_hours"] for p in points),
            },
            "calibration": params,
            "summary": {
                # MW averaged over hourly periods == MWh of energy for the day.
                "expected_wind_mwh_raw": round(total_raw, 1),
                "expected_wind_mwh_calibrated": round(total_cal, 1),
                "adjustment_mwh": round(total_cal - total_raw, 1),
                "p10_mwh": round(sum(p["p10"] for p in points if p["p10"] is not None), 1) or None,
                "p90_mwh": round(sum(p["p90"] for p in points if p["p90"] is not None), 1) or None,
            },
            "points": points,
        }
    finally:
        conn.close()


@router.get("/vintages/{delivery_date}")
def vintages(delivery_date: date) -> dict:
    """Every forecast vintage for a delivery day, flagged either side of the cut-off.

    This is the transparency exhibit: it shows the buyer exactly which
    publications they were and were not allowed to act on.
    """
    _check_range(delivery_date)
    conn = connect()
    try:
        gate = gate_closure_for(delivery_date).strftime("%Y-%m-%dT%H:%M:%SZ")
        win_start, win_end = (
            d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in delivery_window(delivery_date)
        )
        series = []
        for pub in available_vintages(conn, delivery_date):
            rows = conn.execute(
                "SELECT start_time, generation FROM forecasts WHERE publish_time = ? "
                "AND start_time >= ? AND start_time < ? ORDER BY start_time",
                (pub, win_start, win_end),
            ).fetchall()
            series.append({
                "publish_time": pub,
                "available_at_gate_closure": pub <= gate,
                "points": [{"start_time": r["start_time"], "generation": r["generation"]} for r in rows],
            })
        return {"delivery_date": delivery_date.isoformat(), "gate_closure_utc": gate, "vintages": series}
    finally:
        conn.close()
