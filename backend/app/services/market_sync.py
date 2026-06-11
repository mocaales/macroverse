import json
from datetime import UTC, datetime, timedelta

import pandas as pd

from app.core.config import get_settings
from app.repositories.market import MarketObservation, MarketRepository
from app.services.market_data import (
    FRED_SERIES,
    fetch_btc_prices,
    fetch_cryptoquant_series,
    fetch_fred_series,
)

BTC_SERIES_ID = "coinmetrics:btc:PriceUSD:1d"


def _sync_start(full: bool) -> datetime | None:
    return None if full else datetime.now(UTC) - timedelta(days=14)


def _observations(series_id: str, provider: str, frame: pd.DataFrame) -> list[MarketObservation]:
    return [
        MarketObservation(
            series_id=series_id,
            observed_at=row.date.to_pydatetime(),
            provider=provider,
            value=float(row.value),
        )
        for row in frame.itertuples(index=False)
    ]


def sync_fred(
    repository: MarketRepository,
    series_ids: list[str] | None = None,
    *,
    full: bool = False,
) -> dict[str, int]:
    selected = series_ids or list(FRED_SERIES.values())
    names = {series_id: name for name, series_id in FRED_SERIES.items()}
    results = {}
    for fred_id in selected:
        series_id = f"fred:{fred_id}"
        frame = fetch_fred_series(fred_id, _sync_start(full))
        repository.upsert_series(
            series_id=series_id,
            provider="fred",
            name=names.get(fred_id, fred_id),
            symbol=fred_id,
            interval="1d",
            unit="percent",
            metadata={"fred_series_id": fred_id},
        )
        results[series_id] = repository.upsert_observations(_observations(series_id, "fred", frame))
    return results


def sync_bitcoin(repository: MarketRepository, *, full: bool = False) -> dict[str, int]:
    frame = fetch_btc_prices(_sync_start(full))
    repository.upsert_series(
        series_id=BTC_SERIES_ID,
        provider="coinmetrics",
        name="Bitcoin / US Dollar",
        symbol="BTC-USD",
        interval="1d",
        unit="USD",
        metadata={"asset": "btc", "metric": "PriceUSD"},
    )
    count = repository.upsert_observations(_observations(BTC_SERIES_ID, "coinmetrics", frame))
    return {BTC_SERIES_ID: count}


def sync_cryptoquant(
    repository: MarketRepository,
    *,
    series_id: str,
    endpoint: str,
    value_key: str,
    name: str,
    unit: str | None,
    window: str,
    full: bool = False,
) -> dict[str, int]:
    frame = fetch_cryptoquant_series(
        endpoint,
        value_key,
        start=_sync_start(full),
        window=window,
    )
    repository.upsert_series(
        series_id=series_id,
        provider="cryptoquant",
        name=name,
        symbol="BTC",
        interval=window,
        unit=unit,
        metadata={"endpoint": endpoint, "value_key": value_key},
    )
    count = repository.upsert_observations(_observations(series_id, "cryptoquant", frame))
    return {series_id: count}


def sync_configured_cryptoquant(repository: MarketRepository, *, full: bool = False) -> dict[str, int]:
    configured = json.loads(get_settings().cryptoquant_series_json or "[]")
    results = {}
    for item in configured:
        results.update(
            sync_cryptoquant(
                repository,
                series_id=item["series_id"],
                endpoint=item["endpoint"],
                value_key=item["value_key"],
                name=item.get("name", item["series_id"]),
                unit=item.get("unit"),
                window=item.get("window", "day"),
                full=full,
            )
        )
    return results
