import hashlib
from datetime import UTC, date, datetime, time

from google.cloud import firestore
from google.cloud.firestore_v1 import Client, CollectionReference, DocumentSnapshot

from app.models.portfolio import normalize_account_type

LEDGER_COLLECTION = "ledger_entries"
LEGACY_TRADE_COLLECTION = "trades"


def _normalize_datetime(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=UTC)


def _document(snapshot: DocumentSnapshot) -> dict:
    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def _account_id(name: str) -> str:
    normalized = name.strip().casefold().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _normalize_account(row: dict) -> dict:
    normalized = {**row}
    normalized["type"] = normalize_account_type(normalized.get("type", "Trading"))
    normalized["currency"] = normalized.get("currency", "USD")
    return normalized


class PortfolioRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def _user(self, uid: str):
        return self.db.collection("users").document(uid)

    def _collection(self, uid: str, name: str) -> CollectionReference:
        return self._user(uid).collection(name)

    def _ledger_collection(self, uid: str) -> CollectionReference:
        return self._collection(uid, LEDGER_COLLECTION)

    def _legacy_trade_collection(self, uid: str) -> CollectionReference:
        return self._collection(uid, LEGACY_TRADE_COLLECTION)

    def _ledger_reference(self, uid: str, trade_id: str):
        reference = self._ledger_collection(uid).document(trade_id)
        if reference.get().exists:
            return reference
        legacy_reference = self._legacy_trade_collection(uid).document(trade_id)
        return legacy_reference if legacy_reference.get().exists else reference

    def ensure_user(self, uid: str, email: str) -> None:
        self._user(uid).set(
            {"email": email.lower(), "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    def delete_user_data(self, uid: str) -> None:
        self.db.recursive_delete(self._user(uid))

    def list_accounts(self, uid: str) -> list[dict]:
        rows = []
        for snapshot in self._collection(uid, "accounts").stream():
            row = snapshot.to_dict() or {}
            if row.get("type") != "Overall":
                rows.append(_normalize_account(row))
        return sorted(rows, key=lambda row: row["name"].lower())

    def get_account(self, uid: str, name: str) -> dict | None:
        snapshot = self._collection(uid, "accounts").document(_account_id(name)).get()
        return _normalize_account(snapshot.to_dict() or {}) if snapshot.exists else None

    def upsert_account(self, uid: str, payload: dict) -> dict:
        collection = self._collection(uid, "accounts")
        reference = collection.document(_account_id(payload["name"]))
        snapshot = reference.get()
        current = snapshot.to_dict() if snapshot.exists else {}
        record = {
            **payload,
            "created_at": current.get("created_at", datetime.now(UTC)),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        reference.set(record, merge=True)
        return {key: value for key, value in record.items() if key != "updated_at"}

    def delete_account(self, uid: str, name: str) -> bool:
        reference = self._collection(uid, "accounts").document(_account_id(name))
        if not reference.get().exists:
            return False

        for collection_name in (LEDGER_COLLECTION, LEGACY_TRADE_COLLECTION, "recurring_transactions", "investments"):
            collection = self._collection(uid, collection_name)
            for snapshot in collection.stream():
                row = snapshot.to_dict() or {}
                if row.get("account") == name:
                    collection.document(snapshot.id).delete()
        reference.delete()
        return True

    def list_trades(self, uid: str, account: str | None = None) -> list[dict]:
        rows_by_id = {
            snapshot.id: _document(snapshot)
            for snapshot in self._legacy_trade_collection(uid).stream()
        }
        rows_by_id.update({
            snapshot.id: _document(snapshot)
            for snapshot in self._ledger_collection(uid).stream()
        })
        rows = list(rows_by_id.values())
        if account:
            rows = [row for row in rows if row.get("account") == account]
        minimum = datetime.min.replace(tzinfo=UTC)
        return sorted(rows, key=lambda row: row.get("trade_time") or minimum, reverse=True)

    def create_trade(self, uid: str, payload: dict) -> dict:
        trade_date = payload.pop("trade_time")
        record = {
            **payload,
            "trade_time": _normalize_datetime(trade_date),
            "created_at": datetime.now(UTC),
        }
        reference = self._ledger_collection(uid).document()
        reference.set(record)
        return {"id": reference.id, **record}

    def get_trade(self, uid: str, trade_id: str) -> dict | None:
        snapshot = self._ledger_reference(uid, trade_id).get()
        return _document(snapshot) if snapshot.exists else None

    def update_trade(self, uid: str, trade_id: str, payload: dict) -> dict | None:
        reference = self._ledger_reference(uid, trade_id)
        if not reference.get().exists:
            return None
        trade_date = payload.pop("trade_time")
        reference.update(
            {
                **payload,
                "trade_time": _normalize_datetime(trade_date),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )
        return _document(reference.get())

    def delete_trade(self, uid: str, trade_id: str) -> bool:
        references = [
            self._ledger_collection(uid).document(trade_id),
            self._legacy_trade_collection(uid).document(trade_id),
        ]
        existing = [reference for reference in references if reference.get().exists]
        if not existing:
            return False
        for reference in existing:
            reference.delete()
        return True

    def list_assets(self, uid: str, account: str | None = None) -> list[dict]:
        rows = [_document(snapshot) for snapshot in self._collection(uid, "investments").stream()]
        if account:
            rows = [row for row in rows if row.get("account") == account]
        normalized = []
        for row in rows:
            quantity = float(row.get("quantity", 0))
            normalized.append(
                {
                    "id": row["id"],
                    "account": row["account"],
                    "symbol": row.get("symbol", "").upper(),
                    "quantity": quantity,
                    "unit": row.get("unit", "units"),
                    "display_quantity": float(row.get("display_quantity", quantity)),
                    "created_at": row.get("created_at"),
                }
            )
        minimum = datetime.min.replace(tzinfo=UTC)
        return sorted(normalized, key=lambda row: row.get("created_at") or minimum, reverse=True)

    def create_asset(self, uid: str, payload: dict) -> dict:
        record = {
            **payload,
            "symbol": payload["symbol"].upper(),
            "display_quantity": payload.get("display_quantity") or payload["quantity"],
            "created_at": datetime.now(UTC),
        }
        reference = self._collection(uid, "investments").document()
        reference.set(record)
        return {"id": reference.id, **record}

    def delete_asset(self, uid: str, asset_id: str) -> bool:
        reference = self._collection(uid, "investments").document(asset_id)
        if not reference.get().exists:
            return False
        reference.delete()
        return True

    def favourites(self, uid: str) -> list[str]:
        row = self._user(uid).get().to_dict() or {}
        return sorted(row.get("favourites", []))

    def toggle_favourite(self, uid: str, chart_name: str) -> list[str]:
        reference = self._user(uid)
        transaction = self.db.transaction()

        @firestore.transactional
        def update(transaction):
            row = reference.get(transaction=transaction).to_dict() or {}
            favourites = set(row.get("favourites", []))
            favourites.symmetric_difference_update({chart_name})
            result = sorted(favourites)
            transaction.set(reference, {"favourites": result}, merge=True)
            return result

        return update(transaction)
