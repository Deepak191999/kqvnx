"""Bias calibration for the WINDFOR forecast.

Across January 2026 the published forecast exceeds metered outturn in ~84% of
delivery hours, with a mean bias of roughly +1.7 GW. An error that one-sided is
not noise, so it should not be handled by widening a risk band -- it should be
removed. The most plausible drivers are scope and curtailment: WINDFOR projects
what the wind fleet could generate, while FUELHH meters what it was actually
allowed to deliver after Balancing Mechanism bid-offs and network constraints.
The bias is largest in the top outturn quintiles, which is exactly when
constraint curtailment binds, and that is consistent with this reading.

We correct multiplicatively (forecast x k) rather than additively, because the
gap scales with the size of the forecast. k is always fitted on delivery days
strictly before the one being corrected, so nothing here peeks at the future.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# A calibration fitted on only a day or two of history is noise. Below this we
# return no correction at all and the product falls back to the raw forecast.
MIN_HISTORY_DAYS = 7


def fit(history: pd.DataFrame) -> dict | None:
    """Fit the correction factor on completed delivery days.

    `history` must hold paired `forecast`/`actual` hours. Returns None when
    there is not yet enough settled history to fit responsibly.
    """
    if history.empty or history["delivery_date"].nunique() < MIN_HISTORY_DAYS:
        return None

    fc_sum = float(history["forecast"].sum())
    if fc_sum <= 0:
        return None

    err = (history["forecast"] - history["actual"]).to_numpy(dtype=float)
    return {
        "k": round(float(history["actual"].sum()) / fc_sum, 4),
        "additive_bias": round(float(np.mean(err)), 1),
        "over_forecast_rate_pct": round(float(np.mean(err > 0) * 100), 1),
        "fitted_on_days": int(history["delivery_date"].nunique()),
        "fitted_on_hours": int(len(history)),
    }


def apply(forecast_mw: float, params: dict | None) -> float:
    return forecast_mw if not params else round(forecast_mw * params["k"], 1)


def fit_for_day(month_df: pd.DataFrame, delivery_date: str) -> dict | None:
    """Calibration usable on `delivery_date`, fitted only on earlier days."""
    if month_df.empty:
        return None
    return fit(month_df[month_df["delivery_date"] < delivery_date])


def walk_forward(month_df: pd.DataFrame) -> pd.DataFrame:
    """Replay the month as it would have run live.

    For each delivery day the factor is refitted on every day that had already
    settled by then, so the resulting errors are genuinely out of sample. This
    is the evidence behind the improvement figure shown to the client.
    """
    if month_df.empty:
        return pd.DataFrame()

    frames = []
    for day in sorted(month_df["delivery_date"].unique()):
        params = fit_for_day(month_df, day)
        if params is None:
            continue
        cur = month_df[month_df["delivery_date"] == day].copy()
        cur["calibrated"] = cur["forecast"] * params["k"]
        cur["k"] = params["k"]
        frames.append(cur)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def comparison(month_df: pd.DataFrame) -> dict:
    """Raw vs calibrated accuracy over the out-of-sample replay."""
    oos = walk_forward(month_df)
    if oos.empty:
        return {"available": False}

    actual = oos["actual"].to_numpy(dtype=float)
    out = {"available": True, "evaluated_days": int(oos["delivery_date"].nunique()),
           "evaluated_hours": int(len(oos)), "min_history_days": MIN_HISTORY_DAYS,
           "latest_k": float(oos["k"].iloc[-1])}

    for label, col in (("raw", "forecast"), ("calibrated", "calibrated")):
        err = oos[col].to_numpy(dtype=float) - actual
        out[label] = {
            "mae": round(float(np.mean(np.abs(err))), 1),
            "rmse": round(float(np.sqrt(np.mean(err**2))), 1),
            "bias": round(float(np.mean(err)), 1),
        }

    out["mae_improvement_pct"] = round(
        (1 - out["calibrated"]["mae"] / out["raw"]["mae"]) * 100, 1
    )
    out["rmse_improvement_pct"] = round(
        (1 - out["calibrated"]["rmse"] / out["raw"]["rmse"]) * 100, 1
    )
    return out
