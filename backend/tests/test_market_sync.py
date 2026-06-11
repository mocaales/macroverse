from datetime import UTC, datetime

import pandas as pd

from app.services.market_sync import _observations, _sync_start


def test_routine_sync_uses_recent_provider_window():
    start = _sync_start(full=False)

    assert start is not None
    assert 6 <= (datetime.now(UTC) - start).days <= 7


def test_full_sync_requests_complete_provider_history():
    assert _sync_start(full=True) is None


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
