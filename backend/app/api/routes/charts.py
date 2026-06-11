from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Error as PsycopgError

from app.api.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_market_repository,
    get_portfolio_repository,
)
from app.models.charts import ChartDefinition, ChartSeries
from app.repositories.market import MarketRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.market_data import FRED_SERIES, btc_prices, fred_series
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


@router.get("", response_model=list[ChartDefinition])
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


@router.get("/favourites", response_model=list[str])
def favourites(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> list[str]:
    return repository.favourites(user.uid)


@router.post("/favourites/{chart_name}", response_model=list[str])
def toggle_favourite(
    chart_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> list[str]:
    return repository.toggle_favourite(user.uid, chart_name)


@router.get("/{slug}/series", response_model=list[ChartSeries])
def chart_series(
    slug: str,
    market_repository: Annotated[MarketRepository | None, Depends(get_market_repository)],
) -> list[dict]:
    if slug in {
        "bitcoin_cycles_roi",
        "bitcoin_cycles_roi_peak",
        "qt_ending_bear_markets",
        "year_to_date_roi",
        "bitcoin_historical_returns",
    }:
        stored = _read_stored_series(market_repository, BTC_SERIES_ID)
        if stored:
            return [{"name": "BTC / USD", "points": stored}]
        frame = btc_prices()
        return [
            {
                "name": "BTC / USD",
                "points": [
                    {"date": row.date.date().isoformat(), "value": float(row.value)}
                    for row in frame.itertuples(index=False)
                ],
            }
        ]
    if slug in {"treasury_yield_curve", "treasury_yield_spreads"}:
        series = []
        for name, series_id in FRED_SERIES.items():
            stored = _read_stored_series(market_repository, f"fred:{series_id}")
            if stored:
                series.append({"name": name, "points": stored})
                continue
            frame = fred_series(series_id)
            series.append(
                {
                    "name": name,
                    "points": [
                        {"date": str(row.date), "value": float(row.value)} for row in frame.itertuples(index=False)
                    ],
                }
            )
        return series
    raise HTTPException(status_code=404, detail="Chart data is not available.")


def _read_stored_series(repository: MarketRepository | None, series_id: str) -> list[dict]:
    if repository is None:
        return []
    try:
        rows = repository.read_series(series_id)
    except PsycopgError:
        return []
    return [
        {
            "date": row["observed_at"].date().isoformat(),
            "value": float(row["value"] if row["value"] is not None else row["close"]),
        }
        for row in rows
        if row["value"] is not None or row["close"] is not None
    ]
