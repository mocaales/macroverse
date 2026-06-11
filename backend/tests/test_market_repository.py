from datetime import UTC, datetime

from app.repositories.market import MarketRepository


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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


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
