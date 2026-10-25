"""Contract tests for the HTTP surface the React client depends on."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(seeded):
    return TestClient(app)


class TestOps:
    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_meta_describes_the_scope_and_sources(self, client):
        body = client.get("/api/meta").json()
        assert body["delivery_date_from"] == "2026-01-02"
        assert body["delivery_date_to"] == "2026-02-01"
        assert "11:00" in body["gate_closure_local"]
        assert "WINDFOR" in body["sources"]["forecast"]


class TestDecision:
    def test_returns_the_gate_closure_vintage(self, client):
        body = client.get("/api/decision/2026-01-10").json()
        assert body["vintage_used"] == "2026-01-09T09:30:00Z"
        assert body["gate_closure_utc"] == "2026-01-09T11:00:00Z"
        assert len(body["points"]) == 24

    def test_exposes_how_many_vintages_were_withheld(self, client):
        body = client.get("/api/decision/2026-01-10").json()
        assert body["vintages_available_total"] == 3

    def test_rejects_days_outside_the_ingested_window(self, client):
        assert client.get("/api/decision/2025-06-01").status_code == 404

    def test_rejects_an_unparseable_date(self, client):
        assert client.get("/api/decision/not-a-date").status_code == 422


class TestAccuracy:
    def test_summary_is_unavailable_without_paired_history(self, client):
        """The seeded fixture holds one day, which is below the usable floor."""
        body = client.get("/api/accuracy/summary")
        assert body.status_code in (200, 503)

    def test_by_day_returns_one_row_per_delivery_day(self, client):
        rows = client.get("/api/accuracy/by-day").json()
        assert len(rows) == 1
        assert rows[0]["delivery_date"] == "2026-01-10"
        assert rows[0]["mae"] == 500.0

    def test_by_hour_covers_the_day(self, client):
        assert len(client.get("/api/accuracy/by-hour").json()) == 24

    def test_series_exposes_the_paired_columns(self, client):
        rows = client.get("/api/accuracy/series").json()
        assert set(rows[0]) >= {"start_time", "forecast", "actual", "error", "horizon_hours"}
