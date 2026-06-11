from datetime import date

import pytest
from fastapi import HTTPException

from app.api.dependencies import AuthenticatedUser
from app.api.routes import portfolio
from app.models.portfolio import AccountCreate, AssetCreate, TradeCreate, TradeUpdate


class Repository:
    def __init__(self):
        self.calls = []
        self.account = {"name": "Main", "starting_balance": 1000}
        self.updated = {"id": "t1"}
        self.deleted = True

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            if name == "list_accounts":
                return [{"name": "Main"}]
            if name in {"upsert_account", "create_trade", "create_asset"}:
                return args[-1]
            if name == "update_trade":
                return self.updated
            if name in {"delete_trade", "delete_asset"}:
                return self.deleted
            if name == "list_trades":
                return [{"action": "Trade", "pnl": 100, "trade_time": date(2026, 1, 1)}]
            if name == "list_assets":
                return [{"id": "a1"}]
            if name == "get_account":
                return self.account
            return None
        return call


USER = AuthenticatedUser(uid="u1", email="user@example.com")


def test_account_asset_and_list_routes_delegate_to_repository():
    repository = Repository()
    assert portfolio.accounts(USER, repository) == [{"name": "Main"}]
    account = AccountCreate(name=" Main ", starting_balance=100, type="Trading")
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

    monkeypatch.setattr(portfolio, "dashboard_summary", lambda account, trades: {"account": account, "trades": trades})
    monkeypatch.setattr(portfolio, "journal_summary", lambda trades: {"trades": trades})
    assert portfolio.dashboard("Main", USER, repository)["account"]["name"] == "Main"
    assert portfolio.journal("Main", USER, repository)["trades"]


def test_missing_updates_deletes_and_accounts_raise_not_found():
    repository = Repository()
    repository.updated = None
    repository.deleted = False
    repository.account = None
    payload = TradeUpdate(trade_time=date(2026, 1, 1), action="Trade", symbol="BTC", pnl=5)
    for operation in (
        lambda: portfolio.update_trade("missing", payload, USER, repository),
        lambda: portfolio.delete_trade("missing", USER, repository),
        lambda: portfolio.delete_asset("missing", USER, repository),
        lambda: portfolio.dashboard("missing", USER, repository),
    ):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 404
