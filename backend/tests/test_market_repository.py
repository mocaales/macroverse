from datetime import UTC, datetime

import pytest

from app.repositories.market import MarketObservation, MarketRepository


class FakeCursor:
    def __init__(self, latest: datetime | None) -> None:
        self.latest = latest
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query: str, parameters: tuple) -> None:
        self.query = query

    def fetchone(self):
        return (self.latest,)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self, **_kwargs) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1


class FakePool:
    def __init__(self, cursor: FakeCursor) -> None:
        self._connection = FakeConnection(cursor)

    def connection(self) -> FakeConnection:
        return self._connection


def test_latest_observation_cursor_reads_series_metadata_only():
    latest = datetime(2026, 6, 10, tzinfo=UTC)
    cursor = FakeCursor(latest)
    repository = MarketRepository(FakePool(cursor))

    result = repository.latest_observation_at("fred:DGS10")

    assert result == latest
    assert "market_series" in cursor.query
    assert "market_observations" not in cursor.query


class RecordingCursor(FakeCursor):
    def __init__(self) -> None:
        super().__init__(None)
        self.queries: list[str] = []

    def execute(self, query: str, parameters=None) -> None:
        self.queries.append(query)


def test_observation_upserts_use_small_committed_batches_without_pipeline():
    cursor = RecordingCursor()
    pool = FakePool(cursor)
    repository = MarketRepository(pool, batch_size=2)
    observations = [
        MarketObservation(
            series_id="fred:DGS10",
            observed_at=datetime(2026, 6, day, tzinfo=UTC),
            provider="fred",
            value=float(day),
        )
        for day in range(1, 6)
    ]

    count = repository.upsert_observations(observations)

    insert_queries = [query for query in cursor.queries if "INSERT INTO market_observations" in query]
    assert count == 5
    assert len(insert_queries) == 3
    assert pool._connection.commits == 3


def test_series_queries_health_and_validation():
    cursor = RecordingCursor()
    cursor.fetchall = lambda: [{"observed_at": datetime(2026, 1, 1, tzinfo=UTC), "value": 1}]
    cursor.fetchone = lambda: (1,)
    pool = FakePool(cursor)
    repository = MarketRepository(pool)
    repository.upsert_series(
        series_id="fred:DGS10",
        provider="fred",
        name="10 Year",
        symbol="DGS10",
        interval="1d",
        unit="percent",
    )
    rows = repository.read_series(
        "fred:DGS10",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert rows[0]["value"] == 1
    assert repository.healthcheck() is True
    assert repository.upsert_observations([]) == 0

    with pytest.raises(ValueError):
        MarketRepository(pool, batch_size=0)
    with pytest.raises(ValueError):
        repository.upsert_observations(
            [
                MarketObservation("one", datetime.now(UTC), "x"),
                MarketObservation("two", datetime.now(UTC), "x"),
            ]
        )
