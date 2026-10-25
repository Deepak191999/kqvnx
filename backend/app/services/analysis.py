"""Pairing of forecasts with outturn, and the error statistics built on top.

Sign convention used everywhere: error = forecast - actual.
  error > 0  the forecast promised wind that did not arrive. The buyer bought
             too little thermal power and is short at delivery.
  error < 0  wind over-delivered; the buyer is long and sells back at a loss.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.core.config import DELIVERY_DATE_FROM, DELIVERY_DATE_TO
from app.services.vintage import as_of_forecast, delivery_window

# Horizon buckets used for the "does accuracy decay with lead time?" exhibit.
HORIZON_BINS = [0, 6, 12, 18, 24, 30, 36, 48, 72]


def hourly_actuals(conn, start: datetime, end: datetime) -> pd.DataFrame:
    """Half-hourly metered WIND averaged onto the hourly WINDFOR grid.

    Averaging the two settlement periods inside an hour keeps the comparison on
    real measurements. Interpolating the forecast up to half-hourly instead
    would manufacture values that Elexon never published.
    """
    rows = conn.execute(
        "SELECT start_time, generation FROM actuals "
        "WHERE start_time >= ? AND start_time < ? ORDER BY start_time",
        (_iso(start), _iso(end)),
    ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["start_time", "actual"])

    df = pd.DataFrame([dict(r) for r in rows])
    df["ts"] = pd.to_datetime(df["start_time"], utc=True)
    hourly = (
        df.set_index("ts")["generation"]
        .resample("1h")
        .agg(["mean", "count"])
        .rename(columns={"mean": "actual"})
    )
    # Only keep hours where both settlement periods were metered.
    hourly = hourly[hourly["count"] == 2].drop(columns="count").reset_index()
    hourly["start_time"] = hourly["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return hourly[["start_time", "actual"]]


def decision_frame(conn, delivery_day: date) -> pd.DataFrame:
    """Gate-closure forecast joined to outturn for one delivery day."""
    fc = pd.DataFrame(as_of_forecast(conn, delivery_day))
    if fc.empty:
        return pd.DataFrame(
            columns=["start_time", "forecast", "actual", "error", "horizon_hours"]
        )
    fc = fc.rename(columns={"generation": "forecast"})

    win_start, win_end = delivery_window(delivery_day)
    act = hourly_actuals(conn, win_start, win_end)

    df = fc.merge(act, on="start_time", how="left")
    df["error"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error"].abs()
    return df


def month_frame(
    conn, start: date = DELIVERY_DATE_FROM, end: date = DELIVERY_DATE_TO
) -> pd.DataFrame:
    """Every delivery day in scope, each at its own gate-closure vintage.

    This is the backbone of the accuracy analysis: one row per delivery hour,
    always using only what was knowable before that day's auction closed.
    """
    frames = []
    day = start
    while day <= end:
        df = decision_frame(conn, day)
        if not df.empty:
            frames.append(df.assign(delivery_date=day.isoformat()))
        day += timedelta(days=1)
    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True).dropna(subset=["actual"])
    out["hour_of_day"] = pd.to_datetime(out["start_time"], utc=True).dt.hour
    return out


def all_horizon_frame(
    conn, start: date = DELIVERY_DATE_FROM, end: date = DELIVERY_DATE_TO
) -> pd.DataFrame:
    """Every (vintage, target hour) pair, not just the gate-closure one.

    Used to show how forecast skill improves as the delivery hour approaches --
    context for why the 11:00 D-1 cut-off costs the buyer accuracy.
    """
    win_start, _ = delivery_window(start)
    _, win_end = delivery_window(end)
    rows = conn.execute(
        "SELECT publish_time, start_time, generation AS forecast FROM forecasts "
        "WHERE start_time >= ? AND start_time < ?",
        (_iso(win_start), _iso(win_end)),
    ).fetchall()
    if not rows:
        return pd.DataFrame()

    fc = pd.DataFrame([dict(r) for r in rows])
    act = hourly_actuals(conn, win_start, win_end)
    df = fc.merge(act, on="start_time", how="inner")
    df["horizon_hours"] = (
        pd.to_datetime(df["start_time"], utc=True)
        - pd.to_datetime(df["publish_time"], utc=True)
    ).dt.total_seconds() / 3600.0
    df = df[df["horizon_hours"] >= 0].copy()
    df["error"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error"].abs()
    return df


# --- statistics -------------------------------------------------------------


def error_stats(df: pd.DataFrame) -> dict:
    """Headline accuracy metrics for a set of paired forecast/actual hours."""
    d = df.dropna(subset=["error"])
    if d.empty:
        return {}
    err = d["error"].to_numpy(dtype=float)
    act = d["actual"].to_numpy(dtype=float)
    mean_actual = float(np.mean(act))

    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))

    return {
        "n": int(len(err)),
        "mae": _r(mae),
        "rmse": _r(rmse),
        "bias": _r(np.mean(err)),
        # Normalising by mean outturn makes the error comparable across periods;
        # a raw MW figure means little without knowing how windy the period was.
        "nmae_pct": _r(mae / mean_actual * 100) if mean_actual else None,
        "nrmse_pct": _r(rmse / mean_actual * 100) if mean_actual else None,
        "mean_actual": _r(mean_actual),
        "mean_forecast": _r(np.mean(d["forecast"].to_numpy(dtype=float))),
        "max_abs_error": _r(np.max(np.abs(err))),
        "p10": _r(np.percentile(err, 10)),
        "p50": _r(np.percentile(err, 50)),
        "p90": _r(np.percentile(err, 90)),
    }


def stats_by(df: pd.DataFrame, column: str) -> list[dict]:
    """Error statistics grouped by any column (hour of day, delivery date...)."""
    out = []
    for key, grp in df.groupby(column, sort=True):
        s = error_stats(grp)
        if s:
            out.append({column: key, **s})
    return out


def stats_by_horizon(df: pd.DataFrame) -> list[dict]:
    d = df.copy()
    d["bucket"] = pd.cut(d["horizon_hours"], bins=HORIZON_BINS, right=False)
    out = []
    for bucket, grp in d.groupby("bucket", observed=True, sort=True):
        s = error_stats(grp)
        if s:
            out.append(
                {
                    "horizon_from": int(bucket.left),
                    "horizon_to": int(bucket.right),
                    "label": f"{int(bucket.left)}-{int(bucket.right)}h",
                    **s,
                }
            )
    return out


def error_histogram(df: pd.DataFrame, bins: int = 25) -> list[dict]:
    """Empirical distribution of gate-closure error, for the risk view."""
    d = df.dropna(subset=["error"])
    if d.empty:
        return []
    counts, edges = np.histogram(d["error"].to_numpy(dtype=float), bins=bins)
    return [
        {
            "from": _r(edges[i]),
            "to": _r(edges[i + 1]),
            "mid": _r((edges[i] + edges[i + 1]) / 2),
            "count": int(counts[i]),
        }
        for i in range(len(counts))
    ]


def uncertainty_band(month_df: pd.DataFrame, forecasts: list[dict]) -> list[dict]:
    """Attach an empirical P10/P90 range to each forecast hour.

    The band is the historical distribution of gate-closure errors for the same
    hour of day, subtracted from the forecast. It is deliberately empirical --
    no distributional assumption -- so the buyer sees the spread actually
    observed in January rather than a modelled one.
    """
    if month_df.empty:
        return [{**f, "p10": None, "p90": None} for f in forecasts]

    by_hour = {
        int(h): (
            float(np.percentile(g["error"], 10)),
            float(np.percentile(g["error"], 90)),
        )
        for h, g in month_df.groupby("hour_of_day")
    }
    overall = (
        float(np.percentile(month_df["error"], 10)),
        float(np.percentile(month_df["error"], 90)),
    )

    out = []
    for f in forecasts:
        hour = datetime.fromisoformat(f["start_time"].replace("Z", "+00:00")).hour
        lo_err, hi_err = by_hour.get(hour, overall)
        # error = forecast - actual, so actual = forecast - error.
        out.append(
            {
                **f,
                "p10": _r(max(f["generation"] - hi_err, 0.0)),
                "p90": _r(max(f["generation"] - lo_err, 0.0)),
            }
        )
    return out


def _r(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if np.isnan(v) else round(v, 1)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
