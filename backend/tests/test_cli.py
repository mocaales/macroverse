from psycopg import sql

from app import cli


class FakeCursor:
    def __init__(self, applied: list[str]) -> None:
        self.applied = applied
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, parameters=None) -> None:
        self.queries.append(query)

    def fetchall(self):
        return [(name,) for name in self.applied]


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        self.committed = True


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def connection(self):
        return self._connection


def test_migrate_executes_packaged_migrations_as_trusted_sql(monkeypatch):
    cursor = FakeCursor(
        [
            "001_market_data.sql",
            "002_replace_coingecko_series.sql",
            "003_series_sync_cursor.sql",
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(cli, "get_market_pool", lambda: FakePool(connection))

    cli.migrate()

    trusted_queries = [query for query in cursor.queries if isinstance(query, sql.SQL)]
    assert len(trusted_queries) == 1
    assert connection.committed is True
