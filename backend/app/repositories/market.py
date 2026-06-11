from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class MarketObservation:
    series_id: str
    observed_at: datetime
    provider: str
    value: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None


class MarketRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def upsert_series(
        self,
        *,
        series_id: str,
        provider: str,
        name: str,
        symbol: str | None,
        interval: str,
        unit: str | None,
        metadata: dict | None = None,
    ) -> None:
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO market_series (
                    series_id, provider, name, symbol, interval, unit, metadata, last_synced_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (series_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    name = EXCLUDED.name,
                    symbol = EXCLUDED.symbol,
                    interval = EXCLUDED.interval,
                    unit = EXCLUDED.unit,
                    metadata = market_series.metadata || EXCLUDED.metadata,
                    last_synced_at = now(),
                    updated_at = now()
                """,
                (series_id, provider, name, symbol, interval, unit, Jsonb(metadata or {})),
            )
            connection.commit()

    def upsert_observations(self, observations: Iterable[MarketObservation]) -> int:
        rows = [
            (
                item.series_id,
                item.observed_at,
                item.provider,
                item.value,
                item.open,
                item.high,
                item.low,
                item.close,
                item.volume,
            )
            for item in observations
        ]
        if not rows:
            return 0
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO market_observations (
                    series_id, observed_at, provider, value, open, high, low, close, volume
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id, observed_at) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    value = EXCLUDED.value,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    ingested_at = now()
                """,
                rows,
            )
            connection.commit()
        return len(rows)

    def read_series(
        self,
        series_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20_000,
    ) -> list[dict]:
        clauses = ["series_id = %s"]
        parameters: list = [series_id]
        if start:
            clauses.append("observed_at >= %s")
            parameters.append(start)
        if end:
            clauses.append("observed_at <= %s")
            parameters.append(end)
        parameters.append(limit)
        with self.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT observed_at, value, open, high, low, close, volume
                FROM market_observations
                WHERE {" AND ".join(clauses)}
                ORDER BY observed_at ASC
                LIMIT %s
                """,
                parameters,
            )
            return list(cursor.fetchall())

    def latest_observation_at(self, series_id: str) -> datetime | None:
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT max(observed_at) FROM market_observations WHERE series_id = %s",
                (series_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def healthcheck(self) -> bool:
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
