from datetime import UTC, date, datetime

from app.repositories.portfolio import (
    LEDGER_COLLECTION,
    LEGACY_TRADE_COLLECTION,
    PortfolioRepository,
    _account_id,
    _document,
    _normalize_datetime,
)


class Snapshot:
    def __init__(self, identifier, data=None, exists=True):
        self.id = identifier
        self.data = data
        self.exists = exists

    def to_dict(self):
        return self.data


class Reference:
    def __init__(self, identifier, store):
        self.id = identifier
        self.store = store

    def get(self, **_kwargs):
        return Snapshot(self.id, self.store.get(self.id), self.id in self.store)

    def set(self, data, merge=False):
        self.store[self.id] = {**(self.store.get(self.id, {}) if merge else {}), **data}

    def update(self, data):
        self.store[self.id].update(data)

    def delete(self):
        self.store.pop(self.id, None)

    def collection(self, name):
        return Collection(self.store.setdefault(name, {}))


class Collection:
    def __init__(self, store):
        self.store = store

    def document(self, identifier=None):
        identifier = identifier or f"id-{len(self.store) + 1}"
        return Reference(identifier, self.store)

    def stream(self):
        return [Snapshot(key, value) for key, value in self.store.items()]


class Database:
    def __init__(self):
        self.users = {}

    def collection(self, _name):
        return Collection(self.users)


def test_repository_crud_contract():
    db = Database()
    repository = PortfolioRepository(db)
    repository.ensure_user("u1", "USER@EXAMPLE.COM")
    assert db.users["u1"]["email"] == "user@example.com"

    created = repository.upsert_account(
        "u1", {"name": "Main", "starting_balance": 100, "type": "Trading Account", "currency": "EUR"}
    )
    assert created["name"] == "Main"
    assert repository.get_account("u1", "Main")["starting_balance"] == 100
    repository.upsert_account(
        "u1",
        {"name": "main", "starting_balance": 200, "type": "Trading Account", "currency": "EUR"},
    )
    assert repository.list_accounts("u1")[0]["starting_balance"] == 200

    trade = repository.create_trade(
        "u1",
        {"account": "Main", "trade_time": date(2026, 1, 1), "action": "Trade", "symbol": "BTC", "pnl": 10},
    )
    assert trade["id"] in db.users[LEDGER_COLLECTION]
    assert LEGACY_TRADE_COLLECTION not in db.users["u1"]
    assert repository.list_trades("u1", "Main")[0]["id"] == trade["id"]
    updated = repository.update_trade(
        "u1",
        trade["id"],
        {"trade_time": date(2026, 1, 2), "action": "Trade", "symbol": "ETH", "pnl": 20},
    )
    assert updated["symbol"] == "ETH"
    assert repository.update_trade("u1", "missing", {"trade_time": date.today()}) is None
    assert repository.delete_trade("u1", "missing") is False
    assert repository.delete_trade("u1", trade["id"]) is True

    asset = repository.create_asset(
        "u1", {"account": "Main", "symbol": "btc", "quantity": 2, "unit": "units", "display_quantity": None}
    )
    assert asset["symbol"] == "BTC"
    assert repository.list_assets("u1", "Main")[0]["display_quantity"] == 2
    assert repository.delete_asset("u1", "missing") is False
    assert repository.delete_asset("u1", asset["id"]) is True


def test_repository_helpers_and_favourites():
    database = Database()
    deleted = []
    database.recursive_delete = lambda reference: deleted.append(reference.id)
    repository = PortfolioRepository(database)
    repository.ensure_user("u1", "a@example.com")
    repository._user("u1").update({"favourites": ["B", "A"]})
    assert repository.favourites("u1") == ["A", "B"]
    assert _normalize_datetime(None) is None
    now = datetime.now(UTC)
    assert _normalize_datetime(now) is now
    assert _normalize_datetime(date(2026, 1, 1)).tzinfo == UTC
    assert _document(Snapshot("x", None)) == {"id": "x"}
    assert _account_id(" Main ") == _account_id("main")
    repository._collection("u1", "accounts").document(_account_id("Legacy")).set(
        {"name": "Legacy", "starting_balance": 1, "type": "Trading"}
    )
    repository._collection("u1", "accounts").document(_account_id("Old overall")).set(
        {"name": "Old overall", "starting_balance": 0, "type": "Overall"}
    )
    assert repository.get_account("u1", "Legacy")["type"] == "Trading Account"
    assert repository.get_account("u1", "Legacy")["currency"] == "USD"
    assert [row["name"] for row in repository.list_accounts("u1")] == ["Legacy"]
    repository.delete_user_data("u1")
    assert deleted == ["u1"]


def test_delete_account_removes_related_portfolio_records():
    repository = PortfolioRepository(Database())
    repository.upsert_account(
        "u1",
        {"name": "Cleanup", "starting_balance": 0, "type": "Bank Account", "currency": "EUR"},
    )
    repository.upsert_account(
        "u1",
        {"name": "Keep", "starting_balance": 0, "type": "Savings", "currency": "EUR"},
    )
    repository.create_trade(
        "u1",
        {"account": "Cleanup", "trade_time": date(2026, 1, 1), "action": "Deposit", "pnl": 10},
    )
    repository.create_trade(
        "u1",
        {"account": "Keep", "trade_time": date(2026, 1, 1), "action": "Deposit", "pnl": 20},
    )
    repository._collection("u1", "recurring_transactions").document("schedule-1").set(
        {"account": "Cleanup", "description": "Transfer"}
    )
    repository.create_asset(
        "u1",
        {"account": "Cleanup", "symbol": "BTC", "quantity": 1, "unit": "units"},
    )

    assert repository.delete_account("u1", "Cleanup") is True
    assert repository.get_account("u1", "Cleanup") is None
    assert repository.list_trades("u1", "Cleanup") == []
    assert repository._collection("u1", "recurring_transactions").document("schedule-1").get().exists is False
    assert repository.list_assets("u1", "Cleanup") == []
    assert [account["name"] for account in repository.list_accounts("u1")] == ["Keep"]
    assert len(repository.list_trades("u1", "Keep")) == 1
    assert repository.delete_account("u1", "Cleanup") is False


def test_repository_reads_legacy_trades_while_writing_new_ledger_entries():
    db = Database()
    repository = PortfolioRepository(db)
    repository._legacy_trade_collection("u1").document("legacy-1").set({
        "account": "Main",
        "trade_time": datetime(2026, 1, 1, tzinfo=UTC),
        "action": "Trade",
        "symbol": "BTC",
        "pnl": 10,
    })

    created = repository.create_trade(
        "u1",
        {"account": "Main", "trade_time": date(2026, 1, 2), "action": "Trade", "symbol": "ETH", "pnl": 20},
    )

    assert created["id"] in db.users[LEDGER_COLLECTION]
    assert [row["id"] for row in repository.list_trades("u1", "Main")] == [created["id"], "legacy-1"]
    updated = repository.update_trade(
        "u1",
        "legacy-1",
        {"trade_time": date(2026, 1, 3), "action": "Trade", "symbol": "SOL", "pnl": 30},
    )
    assert updated["symbol"] == "SOL"
    assert repository.delete_trade("u1", "legacy-1") is True
    assert repository.get_trade("u1", "legacy-1") is None
