from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Error as PsycopgError

from app.api.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_market_repository,
    get_portfolio_repository,
)
from app.repositories.market import MarketRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.market_data import FRED_SERIES
from app.services.market_sync import BTC_SERIES_ID

CHARTS = [
    (
        "Treasury Yield Spreads",
        "treasury_yield_spreads",
        "Macro",
        ["Rates"],
        [],
        "Slope between two Treasury maturities with optional comparison.",
        True,
    ),
    (
        "Treasury Yield Curve",
        "treasury_yield_curve",
        "Macro",
        ["Rates"],
        [],
        "Term structure across Treasury maturities.",
        True,
    ),
    (
        "Treasury Deposits With Federal Reserve Banks",
        "treasury_deposits",
        "Macro",
        ["Rates"],
        [],
        "Treasury cash balance held at the Federal Reserve.",
        False,
    ),
    (
        "Bitcoin ROI After Cycle Bottom",
        "bitcoin_cycles_roi",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "ROI from each cycle bottom across Bitcoin market cycles.",
        True,
    ),
    (
        "Bitcoin ROI After Cycle Peak",
        "bitcoin_cycles_roi_peak",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "ROI from each market cycle peak.",
        True,
    ),
    (
        "QT Ending Bear Markets",
        "qt_ending_bear_markets",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "Bitcoin performance around quantitative tightening regimes.",
        True,
    ),
    (
        "Year-To-Date ROI",
        "year_to_date_roi",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "Bitcoin annual ROI from January 1.",
        True,
    ),
    (
        "Bitcoin Historical Returns",
        "bitcoin_historical_returns",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "Bitcoin monthly and annual returns.",
        True,
    ),
    (
        "Bitcoin Terminal, Realized & Balanced Price",
        "bitcoin_terminal_realized_balanced_price",
        "Crypto",
        ["Growth"],
        ["BTC"],
        "Bitcoin valuation model bands.",
        False,
    ),
]


router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("")
def charts() -> list[dict]:
    return [
        {
            "name": name,
            "slug": slug,
            "category": category,
            "quick": quick,
            "assets": assets,
            "summary": summary,
            "available": available,
        }
        for name, slug, category, quick, assets, summary, available in CHARTS
    ]


@router.get("/favourites")
def favourites(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> list[str]:
    return repository.favourites(user.uid)


@router.post("/favourites/{chart_name}")
def toggle_favourite(
    chart_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> list[str]:
    return repository.toggle_favourite(user.uid, chart_name)


@router.get(
    "/{slug}/series",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Stored chart data is not available."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Market database is unavailable."},
    },
)
def chart_series(
    slug: str,
    market_repository: Annotated[MarketRepository | None, Depends(get_market_repository)],
) -> list[dict]:
    if market_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market database is not configured.",
        )

    if slug in {
        "bitcoin_cycles_roi",
        "bitcoin_cycles_roi_peak",
        "qt_ending_bear_markets",
        "year_to_date_roi",
        "bitcoin_historical_returns",
    }:
        stored = _read_stored_series(market_repository, BTC_SERIES_ID)
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored Bitcoin market data is not available.",
            )
        return [{"name": "BTC / USD", "points": stored}]

    if slug in {"treasury_yield_curve", "treasury_yield_spreads"}:
        series = []
        for name, series_id in FRED_SERIES.items():
            stored = _read_stored_series(market_repository, f"fred:{series_id}")
            if stored:
                series.append({"name": name, "points": stored})
        if not series:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored Treasury market data is not available.",
            )
        return series

    raise HTTPException(status_code=404, detail="Chart data is not available.")


def _read_stored_series(repository: MarketRepository, series_id: str) -> list[dict]:
    try:
        rows = repository.read_series(series_id)
    except PsycopgError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market database is temporarily unavailable.",
        ) from exc
    return [
        {
            "date": row["observed_at"].date().isoformat(),
            "value": float(row["value"] if row["value"] is not None else row["close"]),
        }
        for row in rows
        if row["value"] is not None or row["close"] is not None
    ]
