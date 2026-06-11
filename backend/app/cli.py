import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.market_database import get_market_pool
from app.repositories.market import MarketRepository
from app.services.market_sync import (
    sync_bitcoin,
    sync_configured_cryptoquant,
    sync_cryptoquant,
    sync_fred,
)


def migrate() -> None:
    pool = get_market_pool()
    if pool is None:
        raise RuntimeError("MARKET_DATABASE_URL is not configured.")
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    with pool.connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}
        for migration in sorted(migration_dir.glob("*.sql")):
            if migration.name in applied:
                continue
            cursor.execute(migration.read_text(encoding="utf-8"))
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Macroverse backend management commands")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate", help="Apply TimescaleDB schema migrations")
    sync_fred_parser = subcommands.add_parser("sync-fred", help="Synchronize FRED series")
    sync_fred_parser.add_argument("series", nargs="*", help="Optional FRED series IDs")
    subcommands.add_parser("sync-bitcoin", help="Synchronize daily Bitcoin/USD history")
    subcommands.add_parser("sync-all", help="Synchronize FRED, Bitcoin, and configured CryptoQuant series")
    cryptoquant = subcommands.add_parser("sync-cryptoquant", help="Synchronize one CryptoQuant series")
    cryptoquant.add_argument("--series-id", required=True)
    cryptoquant.add_argument("--endpoint", required=True)
    cryptoquant.add_argument("--value-key", required=True)
    cryptoquant.add_argument("--name", required=True)
    cryptoquant.add_argument("--unit")
    cryptoquant.add_argument("--window", default="day")
    args = parser.parse_args()
    if args.command == "migrate":
        try:
            migrate()
        finally:
            pool = get_market_pool()
            if pool is not None:
                pool.close()
        return
    pool = get_market_pool()
    if pool is None:
        raise RuntimeError("MARKET_DATABASE_URL is not configured.")
    repository = MarketRepository(pool, batch_size=get_settings().market_database_batch_size)
    try:
        if args.command == "sync-fred":
            print(sync_fred(repository, args.series or None))
        elif args.command == "sync-bitcoin":
            print(sync_bitcoin(repository))
        elif args.command == "sync-all":
            print(
                {
                    **sync_bitcoin(repository),
                    **sync_fred(repository),
                    **sync_configured_cryptoquant(repository),
                }
            )
        elif args.command == "sync-cryptoquant":
            print(
                sync_cryptoquant(
                    repository,
                    series_id=args.series_id,
                    endpoint=args.endpoint,
                    value_key=args.value_key,
                    name=args.name,
                    unit=args.unit,
                    window=args.window,
                )
            )
    finally:
        pool.close()


if __name__ == "__main__":
    main()
