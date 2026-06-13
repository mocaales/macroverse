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
    RecurringTransactionCreate,
    RecurringTransactionResponse,
    TradeCreate,
    TradeResponse,
    TradeUpdate,
)
from app.repositories.portfolio import PortfolioRepository
from app.services.analytics import aggregate_dashboard_summary, dashboard_summary, journal_summary
from app.services.recurring_transactions import sync_recurring_transactions

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


@router.delete(
    "/accounts/{account_name}",
    response_model=Message,
    responses={404: {"description": "Account not found."}},
)
def delete_account(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    if not repository.delete_account(user.uid, account_name):
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"message": "Account and related portfolio data deleted."}


@router.get("/trades", response_model=list[TradeResponse])
def trades(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    account: Annotated[str | None, Query()] = None,
) -> list[dict]:
    sync_recurring_transactions(repository, user.uid)
    return repository.list_trades(user.uid, account)


def _prepare_entry(payload: TradeCreate | TradeUpdate, account: dict) -> dict:
    data = payload.model_dump()
    account_type = account.get("type", "Trading Account")
    if account_type != "Trading Account" and payload.action == "Trade":
        raise HTTPException(status_code=422, detail=f"{account_type} accounts only support deposits and withdrawals.")
    if payload.action == "Trade":
        if not payload.symbol.strip():
            raise HTTPException(status_code=422, detail="A symbol is required for trades.")
        data["symbol"] = payload.symbol.upper()
        return data

    if account_type in {"Savings", "Bank Account"} and not payload.description.strip():
        raise HTTPException(status_code=422, detail="A description is required for cash transactions.")
    if account_type == "Bank Account" and payload.category is None:
        raise HTTPException(status_code=422, detail="A category is required for bank transactions.")
    data["symbol"] = "CASH"
    data["type"] = None
    data["category"] = payload.category or ("Savings" if account_type == "Savings" else None)
    data["pnl"] = -abs(payload.pnl) if payload.action == "Withdraw" else abs(payload.pnl)
    return data


@router.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Account not found."},
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
        raise HTTPException(status_code=404, detail="Account not found.")
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
        raise HTTPException(status_code=404, detail="Trade not found.")
    account = repository.get_account(user.uid, existing["account"])
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    data = _prepare_entry(payload, account)
    trade = repository.update_trade(user.uid, trade_id, data)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return trade


@router.delete(
    "/trades/{trade_id}",
    response_model=Message,
    responses={404: {"description": "Trade not found."}},
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


@router.get("/recurring-transactions", response_model=list[RecurringTransactionResponse])
def recurring_transactions(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
    account: Annotated[str | None, Query()] = None,
) -> list[dict]:
    sync_recurring_transactions(repository, user.uid)
    return repository.list_recurring_transactions(user.uid, account)


@router.post(
    "/recurring-transactions",
    response_model=RecurringTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Account not found."},
        422: {"description": "Only bank accounts support automation."},
    },
)
def create_recurring_transaction(
    payload: RecurringTransactionCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, payload.account)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account["type"] != "Bank Account":
        raise HTTPException(status_code=422, detail="Recurring transactions are only available for bank accounts.")
    schedule = repository.create_recurring_transaction(user.uid, payload.model_dump())
    sync_recurring_transactions(repository, user.uid)
    return schedule


@router.put(
    "/recurring-transactions/{schedule_id}",
    response_model=RecurringTransactionResponse,
    responses={
        404: {"description": "Recurring transaction or account not found."},
        422: {"description": "Only bank accounts support automation."},
    },
)
def update_recurring_transaction(
    schedule_id: str,
    payload: RecurringTransactionCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    account = repository.get_account(user.uid, payload.account)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account["type"] != "Bank Account":
        raise HTTPException(status_code=422, detail="Recurring transactions are only available for bank accounts.")
    schedule = repository.update_recurring_transaction(user.uid, schedule_id, payload.model_dump())
    if not schedule:
        raise HTTPException(status_code=404, detail="Recurring transaction not found.")
    sync_recurring_transactions(repository, user.uid)
    return schedule


@router.delete(
    "/recurring-transactions/{schedule_id}",
    response_model=Message,
    responses={404: {"description": "Recurring transaction not found."}},
)
def delete_recurring_transaction(
    schedule_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    if not repository.delete_recurring_transaction(user.uid, schedule_id):
        raise HTTPException(status_code=404, detail="Recurring transaction not found.")
    return {"message": "Recurring transaction deleted."}


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
    sync_recurring_transactions(repository, user.uid)
    return aggregate_dashboard_summary(
        repository.list_accounts(user.uid),
        repository.list_trades(user.uid),
        currency.upper(),
    )


@router.get(
    "/dashboard/{account_name}",
    response_model=DashboardSummary,
    responses={404: {"description": "Account not found."}},
)
def dashboard(
    account_name: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> dict:
    sync_recurring_transactions(repository, user.uid)
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
    account = repository.get_account(user.uid, account_name)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    if account["type"] != "Trading Account":
        raise HTTPException(status_code=422, detail="The journal is available only for Trading Accounts.")
    return journal_summary(repository.list_trades(user.uid, account_name))
