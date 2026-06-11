from datetime import UTC, date, datetime

from app.repositories.portfolio import PortfolioRepository, _account_id, _document, _normalize_datetime


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

    created = repository.upsert_account("u1", {"name": "Main", "starting_balance": 100, "type": "Trading"})
    assert created["name"] == "Main"
    assert repository.get_account("u1", "Main")["starting_balance"] == 100
    repository.upsert_account("u1", {"name": "main", "starting_balance": 200, "type": "Trading"})
    assert repository.list_accounts("u1")[0]["starting_balance"] == 200

    trade = repository.create_trade(
        "u1",
        {"account": "Main", "trade_time": date(2026, 1, 1), "action": "Trade", "symbol": "BTC", "pnl": 10},
    )
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
    repository = PortfolioRepository(Database())
    repository.ensure_user("u1", "a@example.com")
    repository._user("u1").update({"favourites": ["B", "A"]})
    assert repository.favourites("u1") == ["A", "B"]
    assert _normalize_datetime(None) is None
    now = datetime.now(UTC)
    assert _normalize_datetime(now) is now
    assert _normalize_datetime(date(2026, 1, 1)).tzinfo == UTC
    assert _document(Snapshot("x", None)) == {"id": "x"}
    assert _account_id(" Main ") == _account_id("main")
