from functools import lru_cache

from psycopg_pool import ConnectionPool

from app.core.config import get_settings


@lru_cache
def get_market_pool() -> ConnectionPool | None:
    settings = get_settings()
    if not settings.market_database_url:
        return None
    return ConnectionPool(
        conninfo=settings.market_database_url,
        min_size=settings.market_database_pool_min_size,
        max_size=settings.market_database_pool_max_size,
        open=True,
        kwargs={"autocommit": False},
    )
