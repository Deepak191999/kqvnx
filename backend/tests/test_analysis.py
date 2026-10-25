"""Metric arithmetic and the forecast/outturn alignment rules."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from app.services import analysis


def _frame(forecast, actual):
    df = pd.DataFrame({"forecast": forecast, "actual": actual})
    df["error"] = df["forecast"] - df["actual"]
    return df


class TestErrorStats:
    def test_metrics_match_hand_computation(self):
        # errors: +100, -300, +200  ->  MAE 200, bias 0, RMSE sqrt(140000/3)
        stats = analysis.error_stats(_frame([1100, 700, 1200], [1000, 1000, 1000]))
        assert stats["n"] == 3
        assert stats["mae"] == 200.0
        assert stats["bias"] == 0.0
        assert stats["rmse"] == pytest.approx(216.0, abs=0.5)

    def test_bias_keeps_its_sign(self):
        """Over-forecasting must read positive -- the desk is short, not long."""
        assert analysis.error_stats(_frame([1200, 1300], [1000, 1000]))["bias"] == 250.0
        assert analysis.error_stats(_frame([800, 700], [1000, 1000]))["bias"] == -250.0

    def test_normalisation_is_relative_to_mean_outturn(self):
        stats = analysis.error_stats(_frame([1100, 1100], [1000, 1000]))
        assert stats["nmae_pct"] == 10.0

    def test_empty_input_returns_empty_dict(self):
        assert analysis.error_stats(pd.DataFrame(columns=["forecast", "actual", "error"])) == {}

    def test_rows_without_outturn_are_excluded(self):
        df = _frame([1100, 1200], [1000, None])
        assert analysis.error_stats(df)["n"] == 1


class TestHourlyActuals:
    def test_half_hourly_periods_average_onto_the_hourly_grid(self, seeded):
        out = analysis.hourly_actuals(
            seeded,
            datetime(2026, 1, 10, tzinfo=timezone.utc),
            datetime(2026, 1, 11, tzinfo=timezone.utc),
        )
        assert len(out) == 24
        assert out["actual"].eq(1500.0).all()

    def test_incomplete_hours_are_dropped(self, db):
        """An hour with only one metered period would understate nothing but
        would silently compare against half an hour of data, so we drop it."""
        db.executemany(
            "INSERT INTO actuals VALUES (?,?,?,?)",
            [
                ("2026-01-10T00:00:00Z", "2026-01-10", 1, 1000.0),
                ("2026-01-10T00:30:00Z", "2026-01-10", 2, 2000.0),
                ("2026-01-10T01:00:00Z", "2026-01-10", 3, 5000.0),  # orphan
            ],
        )
        db.commit()
        out = analysis.hourly_actuals(
            db,
            datetime(2026, 1, 10, tzinfo=timezone.utc),
            datetime(2026, 1, 11, tzinfo=timezone.utc),
        )
        assert len(out) == 1
        assert out.iloc[0]["actual"] == 1500.0


class TestDecisionFrame:
    def test_pairs_gate_closure_forecast_with_outturn(self, seeded):
        df = analysis.decision_frame(seeded, date(2026, 1, 10))
        assert len(df) == 24
        assert df["forecast"].eq(2000.0).all()
        assert df["actual"].eq(1500.0).all()
        assert df["error"].eq(500.0).all()


class TestUncertaintyBand:
    def test_band_brackets_the_forecast_using_observed_error(self):
        history = pd.DataFrame(
            {
                "error": [-100.0, 0.0, 100.0, 200.0],
                "hour_of_day": [0, 0, 0, 0],
                "forecast": [1000.0] * 4,
                "actual": [1100.0, 1000.0, 900.0, 800.0],
            }
        )
        out = analysis.uncertainty_band(
            history, [{"start_time": "2026-01-10T00:00:00Z", "generation": 1000.0}]
        )[0]
        # actual = forecast - error, so the high error percentile sets p10.
        assert out["p10"] < 1000.0 < out["p90"]

    def test_band_never_goes_negative(self):
        history = pd.DataFrame(
            {"error": [900.0, 950.0], "hour_of_day": [0, 0],
             "forecast": [1000.0, 1000.0], "actual": [100.0, 50.0]}
        )
        out = analysis.uncertainty_band(
            history, [{"start_time": "2026-01-10T00:00:00Z", "generation": 100.0}]
        )[0]
        assert out["p10"] >= 0.0

    def test_no_history_yields_no_band(self):
        out = analysis.uncertainty_band(
            pd.DataFrame(), [{"start_time": "2026-01-10T00:00:00Z", "generation": 1000.0}]
        )
        assert out[0]["p10"] is None
