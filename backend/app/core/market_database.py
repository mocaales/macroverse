from functools import lru_cache

from psycopg_pool import ConnectionPool

from app.core.config import get_settings


@lru_cache
def get_market_pool() -> ConnectionPool | None:
    settings = get_settings()
    conninfo = settings.market_database_conninfo
    if not conninfo:
        return None
    return ConnectionPool(
        conninfo=conninfo,
        min_size=settings.market_database_pool_min_size,
        max_size=settings.market_database_pool_max_size,
        open=True,
        kwargs={"autocommit": False},
    )
