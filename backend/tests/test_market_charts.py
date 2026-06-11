from datetime import UTC, datetime

import pandas as pd
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


def test_read_stored_series_handles_unconfigured_database():
    assert _read_stored_series(None, "coinmetrics:btc:PriceUSD:1d") == []


def test_chart_catalogue_favourites_and_provider_fallback(monkeypatch):
    user = AuthenticatedUser(uid="u1", email="user@example.com")

    class Portfolio:
        def favourites(self, uid):
            return ["Yield"]

        def toggle_favourite(self, uid, name):
            return [name]

    assert len(charts.charts()) == len(charts.CHARTS)
    assert charts.favourites(user, Portfolio()) == ["Yield"]
    assert charts.toggle_favourite("Bitcoin", user, Portfolio()) == ["Bitcoin"]

    frame = pd.DataFrame([{"date": pd.Timestamp("2026-01-01T00:00:00Z"), "value": 10}])
    monkeypatch.setattr(charts, "btc_prices", lambda: frame)
    result = charts.chart_series("year_to_date_roi", None)
    assert result[0]["points"][0]["value"] == 10

    monkeypatch.setattr(charts, "FRED_SERIES", {"10 Year": "DGS10"})
    monkeypatch.setattr(charts, "fred_series", lambda series_id: frame)
    assert charts.chart_series("treasury_yield_curve", None)[0]["name"] == "10 Year"


def test_chart_series_prefers_storage_and_handles_database_errors():
    repository = FakeMarketRepository()
    assert charts.chart_series("bitcoin_cycles_roi", repository)[0]["points"][0]["value"] == 105_000

    class BrokenRepository:
        def read_series(self, series_id):
            raise OperationalError("offline")

    assert _read_stored_series(BrokenRepository(), "x") == []
    with pytest.raises(HTTPException) as error:
        charts.chart_series("unknown", None)
    assert error.value.status_code == 404
