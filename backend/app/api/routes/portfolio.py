from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import AuthenticatedUser, get_current_user, get_portfolio_repository
from app.models.common import Message
from app.models.portfolio import (
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
from app.services.analytics import dashboard_summary, journal_summary

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


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


@router.get("/trades", response_model=list[TradeResponse])
def trades(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    account: Annotated[str | None, Query()] = None,
) -> list[dict]:
    return repository.list_trades(user.uid, account)


@router.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "A symbol is required for trades."}},
)
def create_trade(
    payload: TradeCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    if payload.action == "Trade" and not payload.symbol.strip():
        raise HTTPException(status_code=422, detail="A symbol is required for trades.")
    data = payload.model_dump()
    if payload.action != "Trade":
        data["symbol"] = "CASH"
        data["type"] = None
        data["pnl"] = -abs(payload.pnl) if payload.action == "Withdraw" else abs(payload.pnl)
    else:
        data["symbol"] = payload.symbol.upper()
    return repository.create_trade(user.uid, data)


@router.put(
    "/trades/{trade_id}",
    response_model=TradeResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Trade not found."}},
)
def update_trade(
    trade_id: str,
    payload: TradeUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    data = payload.model_dump()
    if payload.action != "Trade":
        data["symbol"] = "CASH"
        data["type"] = None
        data["pnl"] = -abs(payload.pnl) if payload.action == "Withdraw" else abs(payload.pnl)
    else:
        data["symbol"] = payload.symbol.upper()
    trade = repository.update_trade(user.uid, trade_id, data)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return trade


@router.delete(
    "/trades/{trade_id}",
    response_model=Message,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Trade not found."}},
)
def delete_trade(
    trade_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    deleted = repository.delete_trade(user.uid, trade_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trade not found.")
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
    responses={status.HTTP_404_NOT_FOUND: {"description": "Asset not found."}},
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
    "/dashboard/{account_name}",
    response_model=DashboardSummary,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Account not found."}},
)
def dashboard(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, account_name)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    return dashboard_summary(account, repository.list_trades(user.uid, account_name))


@router.get("/journal/{account_name}/summary", response_model=JournalSummary)
def journal(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    return journal_summary(repository.list_trades(user.uid, account_name))
