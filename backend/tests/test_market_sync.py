from datetime import UTC, datetime, timedelta

import pandas as pd

from app.services.market_sync import _incremental_start, _observations


class FakeMarketRepository:
    def __init__(self, latest: datetime | None) -> None:
        self.latest = latest

    def latest_observation_at(self, series_id: str) -> datetime | None:
        return self.latest


def test_incremental_start_overlaps_last_seven_days():
    latest = datetime(2026, 6, 11, tzinfo=UTC)

    start = _incremental_start(FakeMarketRepository(latest), "fred:DGS10")

    assert start == latest - timedelta(days=7)


def test_incremental_start_is_none_for_an_empty_series():
    assert _incremental_start(FakeMarketRepository(None), "fred:DGS10") is None


def test_observations_convert_dataframe_rows():
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-11T00:00:00Z"),
                "value": 4.25,
            }
        ]
    )

    observations = _observations("fred:DGS10", "fred", frame)

    assert len(observations) == 1
    assert observations[0].series_id == "fred:DGS10"
    assert observations[0].provider == "fred"
    assert observations[0].observed_at == datetime(2026, 6, 11, tzinfo=UTC)
    assert observations[0].value == 4.25
