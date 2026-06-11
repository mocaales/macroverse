from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import Error as PsycopgError

from app.api.dependencies import get_market_repository
from app.models.common import HealthResponse
from app.repositories.market import MarketRepository

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="macroverse-api", timestamp=datetime.now(UTC))


@router.get("/health/market")
def market_health(
    repository: Annotated[MarketRepository | None, Depends(get_market_repository)],
) -> dict:
    if repository is None:
        return {"status": "not_configured"}
    try:
        healthy = repository.healthcheck()
    except PsycopgError:
        healthy = False
    return {"status": "ok" if healthy else "unavailable"}
