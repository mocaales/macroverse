import pytest
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

    def close(self):
        self.closed = True


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


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["sync-fred", "DGS10", "--full"], "fred"),
        (["sync-bitcoin", "--full"], "bitcoin"),
        (["sync-all", "--full"], "all"),
        (
            [
                "sync-cryptoquant",
                "--series-id",
                "cq:test",
                "--endpoint",
                "endpoint",
                "--value-key",
                "value",
                "--name",
                "Metric",
            ],
            "cryptoquant",
        ),
    ],
)
def test_cli_dispatches_sync_commands(monkeypatch, capsys, arguments, expected):
    pool = FakePool(FakeConnection(FakeCursor([])))
    monkeypatch.setattr(cli, "get_market_pool", lambda: pool)
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: type("Settings", (), {"market_database_batch_size": 10})(),
    )
    calls = []
    monkeypatch.setattr(cli, "sync_fred", lambda *args, **kwargs: calls.append("fred") or {"fred": 1})
    monkeypatch.setattr(cli, "sync_bitcoin", lambda *args, **kwargs: calls.append("bitcoin") or {"btc": 1})
    monkeypatch.setattr(
        cli,
        "sync_configured_cryptoquant",
        lambda *args, **kwargs: calls.append("configured") or {"configured": 1},
    )
    monkeypatch.setattr(
        cli,
        "sync_cryptoquant",
        lambda *args, **kwargs: calls.append("cryptoquant") or {"cq": 1},
    )
    monkeypatch.setattr("sys.argv", ["macroverse", *arguments])
    cli.main()
    assert expected in calls or expected == "all" and calls == ["bitcoin", "fred", "configured"]
    assert capsys.readouterr().out


def test_cli_rejects_missing_database_and_closes_migration_pool(monkeypatch):
    monkeypatch.setattr(cli, "get_market_pool", lambda: None)
    monkeypatch.setattr("sys.argv", ["macroverse", "sync-bitcoin"])
    with pytest.raises(RuntimeError):
        cli.main()

    pool = FakePool(FakeConnection(FakeCursor([])))
    monkeypatch.setattr(cli, "get_market_pool", lambda: pool)
    monkeypatch.setattr(cli, "migrate", lambda: None)
    monkeypatch.setattr("sys.argv", ["macroverse", "migrate"])
    cli.main()
    assert pool.closed is True
