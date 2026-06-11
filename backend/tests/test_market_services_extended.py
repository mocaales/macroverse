import io
import json

import pandas as pd
import pytest
from fastapi import HTTPException

from app.services import market_data, market_sync


class Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Settings:
    fred_api_key = "fred"
    cryptoquant_access_token = "cq"
    cryptoquant_series_json = "[]"
    coinmetrics_api_base_url = "https://example.test"


class Repository:
    def __init__(self):
        self.series = []
        self.observations = []

    def upsert_series(self, **kwargs):
        self.series.append(kwargs)

    def upsert_observations(self, rows):
        self.observations.extend(rows)
        return len(rows)


def test_fred_and_cryptoquant_parsing(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: Settings())
    monkeypatch.setattr(
        market_data,
        "urlopen",
        lambda *args, **kwargs: Response(
            {"observations": [{"date": "2026-01-01", "value": "4.5"}, {"date": "x", "value": "."}]}
        ),
    )
    assert market_data.fetch_fred_series("DGS10").iloc[0]["value"] == 4.5

    monkeypatch.setattr(
        market_data,
        "urlopen",
        lambda *args, **kwargs: Response({"result": {"data": [{"date": "2026-01-01", "metric": "10"}]}}),
    )
    assert market_data.fetch_cryptoquant_series("endpoint", "metric").iloc[0]["value"] == 10


def test_market_provider_configuration_and_errors(monkeypatch):
    settings = Settings()
    settings.fred_api_key = ""
    settings.cryptoquant_access_token = ""
    monkeypatch.setattr(market_data, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as fred_error:
        market_data.fetch_fred_series("DGS10")
    assert fred_error.value.status_code == 503
    with pytest.raises(HTTPException) as cq_error:
        market_data.fetch_cryptoquant_series("endpoint", "metric")
    assert cq_error.value.status_code == 503

    settings.fred_api_key = "fred"
    settings.coinmetrics_api_base_url = "https://example.test"
    monkeypatch.setattr(market_data, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    with pytest.raises(HTTPException) as provider_error:
        market_data.fetch_btc_prices()
    assert provider_error.value.status_code == 502


def test_sync_operations_persist_provider_metadata(monkeypatch):
    frame = pd.DataFrame([{"date": pd.Timestamp("2026-01-01T00:00:00Z"), "value": 5.0}])
    monkeypatch.setattr(market_sync, "fetch_fred_series", lambda *args: frame)
    monkeypatch.setattr(market_sync, "fetch_btc_prices", lambda *args: frame)
    monkeypatch.setattr(market_sync, "fetch_cryptoquant_series", lambda *args, **kwargs: frame)
    repository = Repository()
    assert market_sync.sync_fred(repository, ["DGS10"], full=True)["fred:DGS10"] == 1
    assert market_sync.sync_bitcoin(repository)[market_sync.BTC_SERIES_ID] == 1
    result = market_sync.sync_cryptoquant(
        repository,
        series_id="cq:test",
        endpoint="metric",
        value_key="value",
        name="Metric",
        unit=None,
        window="day",
    )
    assert result == {"cq:test": 1}
    assert {row["provider"] for row in repository.series} == {"fred", "coinmetrics", "cryptoquant"}


def test_configured_cryptoquant_dispatch(monkeypatch):
    settings = Settings()
    settings.cryptoquant_series_json = json.dumps(
        [{"series_id": "cq:test", "endpoint": "metric", "value_key": "value"}]
    )
    monkeypatch.setattr(market_sync, "get_settings", lambda: settings)
    monkeypatch.setattr(market_sync, "sync_cryptoquant", lambda repository, **kwargs: {kwargs["series_id"]: 2})
    assert market_sync.sync_configured_cryptoquant(Repository(), full=True) == {"cq:test": 2}
