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
    def __init__(self, pool: ConnectionPool, *, batch_size: int = 25) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.pool = pool
        self.batch_size = batch_size

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
                    series_id, provider, name, symbol, interval, unit, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    name = EXCLUDED.name,
                    symbol = EXCLUDED.symbol,
                    interval = EXCLUDED.interval,
                    unit = EXCLUDED.unit,
                    metadata = market_series.metadata || EXCLUDED.metadata,
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
        series_ids = {row[0] for row in rows}
        if len(series_ids) != 1:
            raise ValueError("All observations in a batch must belong to the same series")
        rows.sort(key=lambda row: row[1])
        with self.pool.connection() as connection, connection.cursor() as cursor:
            for offset in range(0, len(rows), self.batch_size):
                batch = rows[offset : offset + self.batch_size]
                placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(batch))
                parameters = [value for row in batch for value in row]
                cursor.execute(
                    f"""
                    INSERT INTO market_observations (
                        series_id, observed_at, provider, value, open, high, low, close, volume
                    )
                    VALUES {placeholders}
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
                    parameters,
                )
                latest_observed_at = batch[-1][1]
                series_id = batch[0][0]
                cursor.execute(
                    """
                    UPDATE market_series
                    SET latest_observed_at = GREATEST(
                            COALESCE(latest_observed_at, %s),
                            %s
                        ),
                        last_synced_at = now(),
                        updated_at = now()
                    WHERE series_id = %s
                    """,
                    (latest_observed_at, latest_observed_at, series_id),
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
        page_size: int = 2_000,
    ) -> list[dict]:
        if limit < 1:
            return []
        if page_size < 1:
            raise ValueError("page_size must be at least 1")

        base_clauses = ["series_id = %s"]
        base_parameters: list = [series_id]
        if start:
            base_clauses.append("observed_at >= %s")
            base_parameters.append(start)
        if end:
            base_clauses.append("observed_at <= %s")
            base_parameters.append(end)

        rows: list[dict] = []
        last_observed_at: datetime | None = None
        with self.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
            while len(rows) < limit:
                clauses = list(base_clauses)
                parameters = list(base_parameters)
                if last_observed_at is not None:
                    clauses.append("observed_at > %s")
                    parameters.append(last_observed_at)
                batch_limit = min(page_size, limit - len(rows))
                parameters.append(batch_limit)
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
                batch = list(cursor.fetchall())
                rows.extend(batch)
                if len(batch) < batch_limit:
                    break
                last_observed_at = batch[-1]["observed_at"]
        return rows

    def latest_observation_at(self, series_id: str) -> datetime | None:
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT latest_observed_at FROM market_series WHERE series_id = %s",
                (series_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def healthcheck(self) -> bool:
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
