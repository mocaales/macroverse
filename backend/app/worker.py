import logging
import os
import time

from app.cli import migrate
from app.core.config import get_settings
from app.core.market_database import get_market_pool
from app.repositories.market import MarketRepository
from app.services.market_sync import sync_bitcoin, sync_configured_cryptoquant, sync_fred

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("macroverse.market_worker")


def main() -> None:
    interval = int(os.getenv("MARKET_SYNC_INTERVAL_SECONDS", "3600"))
    migrate()
    pool = get_market_pool()
    if pool is None:
        raise RuntimeError("Market database environment is not configured.")
    repository = MarketRepository(pool, batch_size=get_settings().market_database_batch_size)
    while True:
        started = time.monotonic()
        for name, sync in (
            ("bitcoin", sync_bitcoin),
            ("fred", sync_fred),
            ("cryptoquant", sync_configured_cryptoquant),
        ):
            try:
                logger.info("Starting %s market sync", name)
                logger.info("Completed %s market sync: %s", name, sync(repository))
            except Exception:
                logger.exception("%s market sync failed", name)
        elapsed = time.monotonic() - started
        time.sleep(max(interval - elapsed, 30))


if __name__ == "__main__":
    main()
