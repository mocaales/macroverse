from datetime import date

import pytest
from fastapi import HTTPException

from app.api.dependencies import AuthenticatedUser
from app.api.routes import portfolio
from app.models.portfolio import (
    AccountCreate,
    AssetCreate,
    RecurringTransactionCreate,
    TradeCreate,
    TradeUpdate,
)


class Repository:
    def __init__(self):
        self.calls = []
        self.account = {"name": "Main", "starting_balance": 1000, "type": "Trading Account", "currency": "USD"}
        self.trade = {"id": "t1", "account": "Main"}
        self.updated = {"id": "t1"}
        self.deleted = True

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            if name == "list_accounts":
                return [self.account]
            if name in {"upsert_account", "create_trade", "create_asset", "create_recurring_transaction"}:
                return args[-1]
            if name == "get_trade":
                return self.trade
            if name in {"update_trade", "update_recurring_transaction"}:
                return self.updated
            if name in {"delete_account", "delete_trade", "delete_asset", "delete_recurring_transaction"}:
                return self.deleted
            if name == "list_trades":
                return [{"action": "Trade", "pnl": 100, "trade_time": date(2026, 1, 1)}]
            if name == "list_assets":
                return [{"id": "a1"}]
            if name == "get_account":
                return self.account
            if name == "list_recurring_transactions":
                return []
            return None
        return call


USER = AuthenticatedUser(uid="u1", email="user@example.com")


def test_account_asset_and_list_routes_delegate_to_repository():
    repository = Repository()
    assert portfolio.accounts(USER, repository) == [repository.account]
    account = AccountCreate(name=" Main ", starting_balance=100, type="Trading", currency="EUR")
    assert account.type == "Trading Account"
    assert portfolio.create_account(account, USER, repository)["name"] == "Main"
    assert portfolio.trades(USER, repository, "Main")
    assert portfolio.assets(USER, repository, "Main") == [{"id": "a1"}]
    asset = AssetCreate(account="Main", symbol=" btc ", quantity=1)
    assert portfolio.create_asset(asset, USER, repository)["symbol"] == "btc"


@pytest.mark.parametrize(
    ("action", "symbol", "pnl", "expected_symbol", "expected_pnl"),
    [
        ("Trade", "btc", 10, "BTC", 10),
        ("Deposit", "", -10, "CASH", 10),
        ("Withdraw", "", 10, "CASH", -10),
    ],
)
def test_create_trade_normalizes_ledger_actions(action, symbol, pnl, expected_symbol, expected_pnl):
    repository = Repository()
    payload = TradeCreate(
        account="Main", trade_time=date(2026, 1, 1), action=action, symbol=symbol, pnl=pnl
    )
    result = portfolio.create_trade(payload, USER, repository)
    assert result["symbol"] == expected_symbol
    assert result["pnl"] == expected_pnl


def test_cash_account_rules_require_descriptions_and_bank_categories():
    repository = Repository()
    repository.account = {"name": "Savings", "type": "Savings", "currency": "EUR"}
    with pytest.raises(HTTPException) as description_error:
        portfolio.create_trade(
            TradeCreate(account="Savings", trade_time=date(2026, 1, 1), action="Deposit", pnl=100),
            USER,
            repository,
        )
    assert description_error.value.status_code == 422

    repository.account = {"name": "Current", "type": "Bank Account", "currency": "EUR"}
    with pytest.raises(HTTPException) as category_error:
        portfolio.create_trade(
            TradeCreate(
                account="Current",
                trade_time=date(2026, 1, 1),
                action="Deposit",
                pnl=100,
                description="Salary",
            ),
            USER,
            repository,
        )
    assert category_error.value.status_code == 422

    created = portfolio.create_trade(
        TradeCreate(
            account="Current",
            trade_time=date(2026, 1, 1),
            action="Withdraw",
            pnl=50,
            description="Groceries",
            category="Groceries",
        ),
        USER,
        repository,
    )
    assert created["pnl"] == -50
    assert created["category"] == "Groceries"

    with pytest.raises(HTTPException) as action_error:
        portfolio.create_trade(
            TradeCreate(
                account="Current",
                trade_time=date(2026, 1, 1),
                action="Trade",
                symbol="BTC",
                pnl=10,
            ),
            USER,
            repository,
        )
    assert action_error.value.status_code == 422


def test_trade_requires_symbol():
    with pytest.raises(HTTPException) as error:
        portfolio.create_trade(
            TradeCreate(account="Main", trade_time=date(2026, 1, 1), action="Trade", symbol=" ", pnl=1),
            USER,
            Repository(),
        )
    assert error.value.status_code == 422


def test_update_delete_dashboard_and_journal_paths(monkeypatch):
    repository = Repository()
    payload = TradeUpdate(trade_time=date(2026, 1, 1), action="Withdraw", symbol="BTC", pnl=5)
    assert portfolio.update_trade("t1", payload, USER, repository)["id"] == "t1"
    assert portfolio.delete_trade("t1", USER, repository) == {"message": "Trade deleted."}
    assert portfolio.delete_asset("a1", USER, repository) == {"message": "Asset deleted."}
    assert portfolio.delete_account("Main", USER, repository) == {
        "message": "Account and related portfolio data deleted."
    }

    monkeypatch.setattr(portfolio, "dashboard_summary", lambda account, trades: {"account": account, "trades": trades})
    monkeypatch.setattr(portfolio, "journal_summary", lambda trades: {"trades": trades})
    assert portfolio.dashboard("Main", USER, repository)["account"]["name"] == "Main"
    assert portfolio.journal("Main", USER, repository)["trades"]


def test_journal_is_restricted_to_trading_accounts():
    repository = Repository()
    repository.account = {"name": "Current", "type": "Bank Account", "currency": "EUR"}

    with pytest.raises(HTTPException) as error:
        portfolio.journal("Current", USER, repository)

    assert error.value.status_code == 422
    assert "only for Trading Accounts" in error.value.detail


def test_recurring_and_total_dashboard_routes(monkeypatch):
    repository = Repository()
    repository.account = {"name": "Current", "starting_balance": 100, "type": "Bank Account", "currency": "EUR"}
    payload = RecurringTransactionCreate(
        account="Current",
        action="Deposit",
        amount=100,
        description="Salary",
        category="Salary",
        day_of_month=1,
        start_date=date(2026, 1, 1),
    )
    assert portfolio.create_recurring_transaction(payload, USER, repository)["description"] == "Salary"
    repository.updated = {
        "id": "r1",
        **payload.model_dump(),
        "active": True,
    }
    assert portfolio.update_recurring_transaction("r1", payload, USER, repository)["id"] == "r1"
    assert portfolio.recurring_transactions(USER, repository, "Current") == []
    assert portfolio.delete_recurring_transaction("r1", USER, repository) == {
        "message": "Recurring transaction deleted."
    }

    monkeypatch.setattr(portfolio, "aggregate_dashboard_summary", lambda accounts, trades, currency: {
        "accounts": accounts,
        "trades": trades,
        "currency": currency,
    })
    result = portfolio.total_dashboard(USER, repository, "eur")
    assert result["currency"] == "EUR"

    repository.account["type"] = "Savings"
    with pytest.raises(HTTPException) as error:
        portfolio.create_recurring_transaction(payload, USER, repository)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        portfolio.update_recurring_transaction("r1", payload, USER, repository)
    assert error.value.status_code == 422

    repository.account["type"] = "Bank Account"
    repository.updated = None
    with pytest.raises(HTTPException) as error:
        portfolio.update_recurring_transaction("missing", payload, USER, repository)
    assert error.value.status_code == 404


def test_missing_updates_deletes_and_accounts_raise_not_found():
    repository = Repository()
    repository.updated = None
    repository.deleted = False
    repository.account = None
    repository.trade = None
    payload = TradeUpdate(trade_time=date(2026, 1, 1), action="Trade", symbol="BTC", pnl=5)
    for operation in (
        lambda: portfolio.update_trade("missing", payload, USER, repository),
        lambda: portfolio.delete_trade("missing", USER, repository),
        lambda: portfolio.delete_account("missing", USER, repository),
        lambda: portfolio.delete_asset("missing", USER, repository),
        lambda: portfolio.update_recurring_transaction(
            "missing",
            RecurringTransactionCreate(
                account="Main",
                action="Deposit",
                amount=10,
                description="Salary",
                category="Salary",
                day_of_month=1,
                start_date=date(2026, 1, 1),
            ),
            USER,
            repository,
        ),
        lambda: portfolio.delete_recurring_transaction("missing", USER, repository),
        lambda: portfolio.dashboard("missing", USER, repository),
        lambda: portfolio.journal("missing", USER, repository),
    ):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 404
