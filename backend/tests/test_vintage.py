"""The no-hindsight guarantee. If any of these fail, every number in the
product is suspect, because the app would be showing the buyer information
that did not exist when they had to commit.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.services.vintage import (
    as_of_forecast,
    available_vintages,
    delivery_window,
    gate_closure_for,
)


class TestGateClosure:
    def test_january_closure_is_11_utc(self):
        # UK local time is GMT in January, so 11:00 local == 11:00 UTC on D-1.
        assert gate_closure_for(date(2026, 1, 10)) == datetime(
            2026, 1, 9, 11, 0, tzinfo=timezone.utc
        )

    def test_summer_closure_shifts_with_bst(self):
        # The rule is "11:00 UK local", not "11:00 UTC". Under BST that is
        # 10:00 UTC -- hard-coding UTC would silently admit a later vintage.
        assert gate_closure_for(date(2026, 7, 10)) == datetime(
            2026, 7, 9, 10, 0, tzinfo=timezone.utc
        )

    def test_closure_is_always_on_the_prior_day(self):
        assert gate_closure_for(date(2026, 1, 1)).date() == date(2025, 12, 31)


class TestDeliveryWindow:
    def test_window_is_24_hours(self):
        start, end = delivery_window(date(2026, 1, 10))
        assert (end - start).total_seconds() == 24 * 3600
        assert start == datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)


class TestAsOfForecast:
    def test_selects_latest_vintage_before_gate_closure(self, seeded):
        points = as_of_forecast(seeded, date(2026, 1, 10))
        assert len(points) == 24
        assert {p["publish_time"] for p in points} == {"2026-01-09T09:30:00Z"}
        assert all(p["generation"] == 2000.0 for p in points)

    def test_post_closure_vintage_is_never_used(self, seeded):
        """The 13:30 publication exists and is newer, but is hindsight."""
        points = as_of_forecast(seeded, date(2026, 1, 10))
        assert "2026-01-09T13:30:00Z" not in {p["publish_time"] for p in points}
        assert all(p["generation"] != 3000.0 for p in points)

    def test_earlier_cutoff_falls_back_to_older_vintage(self, seeded):
        points = as_of_forecast(
            seeded,
            date(2026, 1, 10),
            as_of=datetime(2026, 1, 9, 5, 0, tzinfo=timezone.utc),
        )
        assert {p["publish_time"] for p in points} == {"2026-01-09T02:30:00Z"}

    def test_cutoff_before_any_publication_returns_nothing(self, seeded):
        assert as_of_forecast(
            seeded,
            date(2026, 1, 10),
            as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ) == []

    def test_boundary_publication_is_included(self, seeded):
        """A vintage published exactly at the cut-off was available to act on."""
        points = as_of_forecast(
            seeded,
            date(2026, 1, 10),
            as_of=datetime(2026, 1, 9, 9, 30, tzinfo=timezone.utc),
        )
        assert {p["publish_time"] for p in points} == {"2026-01-09T09:30:00Z"}

    def test_horizon_is_measured_from_publication(self, seeded):
        points = as_of_forecast(seeded, date(2026, 1, 10))
        # 09:30 on D-1 to 00:00 on D is 14.5 hours; the last hour is 23h later.
        assert points[0]["horizon_hours"] == 14.5
        assert points[-1]["horizon_hours"] == 37.5

    def test_results_are_ordered_by_target_time(self, seeded):
        points = as_of_forecast(seeded, date(2026, 1, 10))
        assert [p["start_time"] for p in points] == sorted(p["start_time"] for p in points)


class TestAvailableVintages:
    def test_lists_every_publication_including_post_closure(self, seeded):
        assert available_vintages(seeded, date(2026, 1, 10)) == [
            "2026-01-09T02:30:00Z",
            "2026-01-09T09:30:00Z",
            "2026-01-09T13:30:00Z",
        ]
