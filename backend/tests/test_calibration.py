"""Calibration behaviour, with particular attention to data leakage.

The 40% accuracy improvement this product claims is only honest if the factor
behind it was never fitted on the day it is scoring.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.services import calibration


def _history(days: int, forecast: float = 1000.0, actual: float = 800.0) -> pd.DataFrame:
    rows = [
        {"delivery_date": f"2026-01-{d:02d}", "forecast": forecast, "actual": actual}
        for d in range(1, days + 1)
        for _ in range(24)
    ]
    return pd.DataFrame(rows)


class TestFit:
    def test_recovers_a_known_multiplicative_factor(self):
        params = calibration.fit(_history(10, forecast=1000.0, actual=800.0))
        assert params["k"] == 0.8

    def test_reports_additive_bias_and_over_forecast_rate(self):
        params = calibration.fit(_history(10, forecast=1000.0, actual=800.0))
        assert params["additive_bias"] == 200.0
        assert params["over_forecast_rate_pct"] == 100.0

    def test_refuses_to_fit_on_thin_history(self):
        """Below the minimum we return nothing rather than a noisy factor."""
        assert calibration.fit(_history(calibration.MIN_HISTORY_DAYS - 1)) is None

    def test_fits_at_exactly_the_minimum(self):
        assert calibration.fit(_history(calibration.MIN_HISTORY_DAYS)) is not None

    def test_empty_history_returns_none(self):
        assert calibration.fit(pd.DataFrame(columns=["delivery_date", "forecast", "actual"])) is None


class TestApply:
    def test_scales_by_the_fitted_factor(self):
        assert calibration.apply(1000.0, {"k": 0.85}) == 850.0

    def test_passes_the_forecast_through_when_uncalibrated(self):
        assert calibration.apply(1000.0, None) == 1000.0


class TestNoLeakage:
    def test_fit_for_day_excludes_the_day_being_corrected(self):
        """The target day's own outturn must not influence its own correction."""
        df = _history(10)
        # Make the final day wildly different; it must not move the factor.
        df.loc[df["delivery_date"] == "2026-01-10", "actual"] = 1.0

        params = calibration.fit_for_day(df, "2026-01-10")
        assert params["k"] == 0.8  # unchanged by the outlier day

    def test_fit_for_day_uses_only_strictly_earlier_days(self):
        df = _history(10)
        params = calibration.fit_for_day(df, "2026-01-08")
        assert params["fitted_on_days"] == 7

    def test_walk_forward_skips_days_without_enough_history(self):
        out = calibration.walk_forward(_history(10))
        scored = sorted(out["delivery_date"].unique())
        # Days 1-7 cannot be scored; the first with 7 prior days is the 8th.
        assert scored[0] == "2026-01-08"
        assert len(scored) == 3


class TestComparison:
    def test_calibration_reduces_error_on_a_biased_forecast(self):
        result = calibration.comparison(_history(20, forecast=1000.0, actual=800.0))
        assert result["available"] is True
        assert result["calibrated"]["mae"] < result["raw"]["mae"]
        assert result["mae_improvement_pct"] > 0

    def test_unavailable_when_history_is_too_short(self):
        assert calibration.comparison(_history(3))["available"] is False

    def test_unavailable_on_empty_input(self):
        assert calibration.comparison(pd.DataFrame())["available"] is False
