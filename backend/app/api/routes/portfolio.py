from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import AuthenticatedUser, get_current_user, get_portfolio_repository
from app.models.common import Message
from app.models.portfolio import (
    TRADING_ACCOUNT_TYPE,
    AccountCreate,
    AccountResponse,
    AssetCreate,
    AssetResponse,
    DashboardSummary,
    JournalSummary,
    TradeCreate,
    TradeResponse,
    TradeUpdate,
)
from app.repositories.portfolio import PortfolioRepository
from app.services.analytics import aggregate_dashboard_summary, dashboard_summary, journal_summary

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
ACCOUNT_NOT_FOUND = "Account not found."
TRADE_NOT_FOUND = "Trade not found."


@router.get("/accounts", response_model=list[AccountResponse])
def accounts(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> list[dict]:
    repository.ensure_user(user.uid, user.email)
    return repository.list_accounts(user.uid)


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    repository.ensure_user(user.uid, user.email)
    return repository.upsert_account(user.uid, payload.model_dump())


@router.delete(
    "/accounts/{account_name}",
    response_model=Message,
    responses={404: {"description": ACCOUNT_NOT_FOUND}},
)
def delete_account(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    if not repository.delete_account(user.uid, account_name):
        raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND)
    return {"message": "Account and related portfolio data deleted."}


@router.get("/trades", response_model=list[TradeResponse])
def trades(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    account: Annotated[str | None, Query()] = None,
) -> list[dict]:
    return repository.list_trades(user.uid, account)


def _prepare_entry(payload: TradeCreate | TradeUpdate, account: dict) -> dict:
    data = payload.model_dump()
    if account.get("type", TRADING_ACCOUNT_TYPE) != TRADING_ACCOUNT_TYPE:
        raise HTTPException(status_code=422, detail="Only Trading Accounts are supported.")
    if payload.action == "Trade":
        if not payload.symbol.strip():
            raise HTTPException(status_code=422, detail="A symbol is required for trades.")
        data["symbol"] = payload.symbol.upper()
        return data

    data["symbol"] = "CASH"
    data["type"] = None
    data["category"] = payload.category
    data["pnl"] = -abs(payload.pnl) if payload.action == "Withdraw" else abs(payload.pnl)
    return data


@router.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": ACCOUNT_NOT_FOUND},
        422: {"description": "The transaction is not valid for this account type."},
    },
)
def create_trade(
    payload: TradeCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, payload.account)
    if not account:
        raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND)
    return repository.create_trade(user.uid, _prepare_entry(payload, account))


@router.put(
    "/trades/{trade_id}",
    response_model=TradeResponse,
    responses={
        404: {"description": "Trade or account not found."},
        422: {"description": "The transaction is not valid for this account type."},
    },
)
def update_trade(
    trade_id: str,
    payload: TradeUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    existing = repository.get_trade(user.uid, trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail=TRADE_NOT_FOUND)
    account = repository.get_account(user.uid, existing["account"])
    if not account:
        raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND)
    data = _prepare_entry(payload, account)
    trade = repository.update_trade(user.uid, trade_id, data)
    if not trade:
        raise HTTPException(status_code=404, detail=TRADE_NOT_FOUND)
    return trade


@router.delete(
    "/trades/{trade_id}",
    response_model=Message,
    responses={404: {"description": TRADE_NOT_FOUND}},
)
def delete_trade(
    trade_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    deleted = repository.delete_trade(user.uid, trade_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=TRADE_NOT_FOUND)
    return {"message": "Trade deleted."}


@router.get("/assets", response_model=list[AssetResponse])
def assets(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    account: Annotated[str | None, Query()] = None,
) -> list[dict]:
    return repository.list_assets(user.uid, account)


@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    return repository.create_asset(user.uid, payload.model_dump())


@router.delete(
    "/assets/{asset_id}",
    response_model=Message,
    responses={404: {"description": "Asset not found."}},
)
def delete_asset(
    asset_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    deleted = repository.delete_asset(user.uid, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return {"message": "Asset deleted."}


@router.get(
    "/dashboard",
    response_model=DashboardSummary,
)
def total_dashboard(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "EUR",
) -> dict:
    return aggregate_dashboard_summary(
        repository.list_accounts(user.uid),
        repository.list_trades(user.uid),
        currency.upper(),
    )


@router.get(
    "/dashboard/{account_name}",
    response_model=DashboardSummary,
    responses={404: {"description": ACCOUNT_NOT_FOUND}},
)
def dashboard(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, account_name)
    if not account:
        raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND)
    return dashboard_summary(account, repository.list_trades(user.uid, account_name))


@router.get(
    "/journal/{account_name}/summary",
    response_model=JournalSummary,
    responses={
        404: {"description": ACCOUNT_NOT_FOUND},
        422: {"description": "The journal is available only for trading accounts."},
    },
)
def journal(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, account_name)
    if not account:
        raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND)
    if account["type"] != TRADING_ACCOUNT_TYPE:
        raise HTTPException(status_code=422, detail="The journal is available only for Trading Accounts.")
    return journal_summary(repository.list_trades(user.uid, account_name))
