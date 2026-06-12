from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from psycopg import OperationalError

from app.api.dependencies import AuthenticatedUser
from app.api.routes import charts
from app.api.routes.charts import _read_stored_series


class FakeMarketRepository:
    def read_series(self, series_id: str) -> list[dict]:
        assert series_id == "coinmetrics:btc:PriceUSD:1d"
        return [
            {
                "observed_at": datetime(2026, 6, 11, tzinfo=UTC),
                "value": 105_000.0,
                "close": None,
            }
        ]


def test_read_stored_series_formats_database_rows_for_chart_api():
    points = _read_stored_series(FakeMarketRepository(), "coinmetrics:btc:PriceUSD:1d")

    assert points == [{"date": "2026-06-11", "value": 105_000.0}]


def test_chart_catalogue_and_favourites():
    user = AuthenticatedUser(uid="u1", email="user@example.com")

    class Portfolio:
        def favourites(self, uid):
            return ["Yield"]

        def toggle_favourite(self, uid, name):
            return [name]

    assert len(charts.charts()) == len(charts.CHARTS)
    assert charts.favourites(user, Portfolio()) == ["Yield"]
    assert charts.toggle_favourite("Bitcoin", user, Portfolio()) == ["Bitcoin"]


def test_chart_series_requires_market_database():
    with pytest.raises(HTTPException) as error:
        charts.chart_series("year_to_date_roi", None)

    assert error.value.status_code == 503
    assert error.value.detail == "Market database is not configured."


def test_chart_series_reads_bitcoin_from_storage():
    repository = FakeMarketRepository()
    assert charts.chart_series("bitcoin_cycles_roi", repository)[0]["points"][0]["value"] == 105_000


def test_chart_series_reads_available_treasury_storage(monkeypatch):
    class TreasuryRepository:
        def read_series(self, series_id):
            if series_id == "fred:DGS10":
                return [
                    {
                        "observed_at": datetime(2026, 6, 11, tzinfo=UTC),
                        "value": 4.5,
                        "close": None,
                    }
                ]
            return []

    monkeypatch.setattr(charts, "FRED_SERIES", {"10 Year": "DGS10", "30 Year": "DGS30"})

    result = charts.chart_series("treasury_yield_curve", TreasuryRepository())

    assert result == [{"name": "10 Year", "points": [{"date": "2026-06-11", "value": 4.5}]}]


def test_chart_series_handles_missing_storage_and_database_errors(monkeypatch):
    class EmptyRepository:
        def read_series(self, series_id):
            return []

    with pytest.raises(HTTPException) as bitcoin_error:
        charts.chart_series("year_to_date_roi", EmptyRepository())
    assert bitcoin_error.value.status_code == 404

    monkeypatch.setattr(charts, "FRED_SERIES", {"10 Year": "DGS10"})
    with pytest.raises(HTTPException) as treasury_error:
        charts.chart_series("treasury_yield_spreads", EmptyRepository())
    assert treasury_error.value.status_code == 404

    class BrokenRepository:
        def read_series(self, series_id):
            raise OperationalError("offline")

    with pytest.raises(HTTPException) as database_error:
        _read_stored_series(BrokenRepository(), "x")
    assert database_error.value.status_code == 503

    with pytest.raises(HTTPException) as error:
        charts.chart_series("unknown", EmptyRepository())
    assert error.value.status_code == 404
