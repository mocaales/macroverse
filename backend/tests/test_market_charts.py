from datetime import UTC, datetime

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
