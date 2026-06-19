from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from firebase_admin import auth, firestore

from app.core.firebase import get_firebase_app, get_firestore_client
from app.repositories.portfolio import (
    LEDGER_COLLECTION,
    LEGACY_TRADE_COLLECTION,
    _account_id,
)

ACCOUNT_NAME = "Blofin"
ACCOUNT_TYPE = "Trading Account"
ACCOUNT_CURRENCY = "USD"
IMPORT_ID = "blofin_2025_2026"
ACCOUNT_CREATED_AT = datetime(2025, 6, 19, tzinfo=UTC)
CSV_PATTERNS = {
    "deposits": "Deposit_history_*.csv",
    "internal_transfers": "Internal_transfer_history_*.csv",
    "orders": "Order_history_*.csv",
    "positions": "Position_history_*.csv",
    "transfers": "Transfer_history_*.csv",
    "withdrawals": "Withdrawal_history_*.csv",
}


@dataclass(frozen=True)
class ImportPlan:
    account_id: str
    uid: str
    starting_balance: Decimal
    ledger_movement: Decimal
    ledger_rows: list[tuple[str, dict[str, Any]]]
    raw_rows: list[tuple[str, dict[str, Any]]]
    source_counts: dict[str, int]
    existing_ledger_count: int


def parse_datetime(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%m/%d/%Y %H:%M:%S").replace(tzinfo=UTC)


def parse_decimal(value: str | None) -> Decimal:
    if not value or value.strip() == "--":
        return Decimal("0")
    amount = value.strip().split(" ", maxsplit=1)[0].replace(",", "")
    return Decimal(amount)


def decimal_to_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def document_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def read_csv(name: str, path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {name} CSV: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def raw_record(source: str, row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    source_time = row.get("Time") or row.get("Order Time") or row.get("Close Time") or row.get("Open Time")
    raw_id = document_id("raw", source, row_number, row)
    record: dict[str, Any] = {
        "account": ACCOUNT_NAME,
        "source": source,
        "source_row": row_number,
        "row": row,
        "import_id": IMPORT_ID,
        "imported_at": firestore.SERVER_TIMESTAMP,
    }
    if source_time:
        record["source_time"] = parse_datetime(source_time)
    return raw_id, record


def deposit_entry(row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    amount = parse_decimal(row["Amount"])
    entry_id = document_id("blofin_deposit", row_number, row["Time"], row.get("TXID", ""), amount)
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": parse_datetime(row["Time"]),
        "action": "Deposit",
        "type": None,
        "symbol": row["Asset"].strip().upper(),
        "pnl": decimal_to_float(amount),
        "description": f"Blofin deposit via {row.get('Network', 'unknown network')}",
        "notes": f"TXID: {row.get('TXID', '')}. Status: {row.get('Status', '')}.",
        "category": "Transfer",
        "source": "blofin_deposit_history",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def withdrawal_entry(row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    amount = parse_decimal(row["Amount"])
    fee = parse_decimal(row.get("Withdraw Fee"))
    movement = -(amount + fee)
    entry_id = document_id("blofin_withdrawal", row_number, row["Time"], row.get("TXID", ""), amount, fee)
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": parse_datetime(row["Time"]),
        "action": "Withdraw",
        "type": None,
        "symbol": row["Asset"].strip().upper(),
        "pnl": decimal_to_float(movement),
        "description": f"Blofin withdrawal via {row.get('Network', 'unknown network')}",
        "notes": (
            f"TXID: {row.get('TXID', '')}. Address: {row.get('Address', '')}. "
            f"Fee: {row.get('Withdraw Fee', '0')}. Status: {row.get('Status', '')}."
        ),
        "category": "Transfer",
        "source": "blofin_withdrawal_history",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def position_entry(row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    realised_pnl = parse_decimal(row["Realized PNL"])
    entry_id = document_id(
        "blofin_position",
        row_number,
        row["Symbol"],
        row["Open Time"],
        row["Close Time"],
        row["Side"],
    )
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": parse_datetime(row["Close Time"]),
        "action": "Trade",
        "type": row["Side"].strip().title(),
        "symbol": row["Symbol"].strip().upper(),
        "pnl": decimal_to_float(realised_pnl),
        "description": f"{row['Side'].strip().title()} {row['Symbol'].strip().upper()} closed on Blofin",
        "notes": (
            f"Opened: {row['Open Time']}. Avg price: {row['Avg. Price']}. Exit price: {row['Exit Price']}. "
            f"Leverage: {row['Leverage']}. Margin: {row['Margin Mode']}. Closed PNL: {row['Closed PNL']}. "
            f"Trading fee: {row['Trading Fee']}. Funding fee: {row['Funding Fee']}. Status: {row['Status']}."
        ),
        "category": "Other",
        "source": "blofin_position_history",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def transfer_entry(row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    entry_id = document_id("blofin_transfer", row_number, row["Time"], row["From"], row["To"], row["Amount"])
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": parse_datetime(row["Time"]),
        "action": "Deposit",
        "type": None,
        "symbol": row["Coin"].strip().upper(),
        "pnl": 0.0,
        "description": f"Internal transfer from {row['From']} to {row['To']}",
        "notes": f"Amount: {row['Amount']} {row['Coin']}. Status: {row['Status']}.",
        "category": "Transfer",
        "source": "blofin_transfer_history",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def internal_transfer_entry(row_number: int, row: dict[str, str]) -> tuple[str, dict[str, Any]]:
    entry_id = document_id("blofin_internal_transfer", row_number, row)
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": parse_datetime(row["Time"]),
        "action": "Deposit",
        "type": None,
        "symbol": row["Coin"].strip().upper(),
        "pnl": 0.0,
        "description": f"Internal transfer {row.get('Type', '').strip()} with {row.get('To/From', '').strip()}",
        "notes": (
            f"Order ID: {row.get('Order ID', '')}. Amount: {row['Amount']} {row['Coin']}. "
            f"Status: {row['Status']}."
        ),
        "category": "Transfer",
        "source": "blofin_internal_transfer_history",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def source_files(directory: Path) -> dict[str, Path]:
    files = {}
    for source, pattern in CSV_PATTERNS.items():
        matches = sorted(directory.glob(pattern))
        if len(matches) != 1:
            raise FileNotFoundError(f"Expected exactly one {pattern!r} file in {directory}; found {len(matches)}.")
        files[source] = matches[0]
    return files


def load_records(target_balance: Decimal, uid: str, existing_ledger_count: int, csv_directory: Path) -> ImportPlan:
    rows_by_source = {name: read_csv(name, path) for name, path in source_files(csv_directory).items()}
    ledger_rows: list[tuple[str, dict[str, Any]]] = []
    raw_rows: list[tuple[str, dict[str, Any]]] = []

    for source, rows in rows_by_source.items():
        for row_number, row in enumerate(rows, start=1):
            raw_rows.append(raw_record(source, row_number, row))

    for row_number, row in enumerate(rows_by_source["deposits"], start=1):
        if row.get("Status", "").lower() == "completed":
            ledger_rows.append(deposit_entry(row_number, row))

    for row_number, row in enumerate(rows_by_source["withdrawals"], start=1):
        if row.get("Status", "").lower() == "success":
            ledger_rows.append(withdrawal_entry(row_number, row))

    for row_number, row in enumerate(rows_by_source["positions"], start=1):
        if row.get("Status", "").lower() == "closed":
            ledger_rows.append(position_entry(row_number, row))

    for row_number, row in enumerate(rows_by_source["transfers"], start=1):
        if row.get("Status", "").lower() == "success":
            ledger_rows.append(transfer_entry(row_number, row))

    for row_number, row in enumerate(rows_by_source["internal_transfers"], start=1):
        if row.get("Status", "").lower() == "success":
            ledger_rows.append(internal_transfer_entry(row_number, row))

    ledger_movement = sum(Decimal(str(record["pnl"])) for _, record in ledger_rows)
    starting_balance = target_balance - ledger_movement
    return ImportPlan(
        account_id=_account_id(ACCOUNT_NAME),
        uid=uid,
        starting_balance=starting_balance,
        ledger_movement=ledger_movement,
        ledger_rows=ledger_rows,
        raw_rows=raw_rows,
        source_counts={source: len(rows) for source, rows in rows_by_source.items()},
        existing_ledger_count=existing_ledger_count,
    )


def existing_account_ledger_count(db, uid: str) -> int:
    total = 0
    user = db.collection("users").document(uid)
    for collection_name in (LEDGER_COLLECTION, LEGACY_TRADE_COLLECTION):
        for snapshot in user.collection(collection_name).stream():
            row = snapshot.to_dict() or {}
            if row.get("account") == ACCOUNT_NAME:
                total += 1
    return total


def replace_existing_account_data(db, uid: str) -> None:
    user = db.collection("users").document(uid)
    import_reference = user.collection("imports").document(IMPORT_ID)
    db.recursive_delete(import_reference)

    archive_rows = []
    delete_references = []
    for collection_name in (LEDGER_COLLECTION, LEGACY_TRADE_COLLECTION):
        for snapshot in user.collection(collection_name).stream():
            row = snapshot.to_dict() or {}
            if row.get("account") == ACCOUNT_NAME:
                archive_rows.append(
                    (
                        import_reference.collection("replaced_ledger_rows").document(
                            document_id("replaced", collection_name, snapshot.id)
                        ),
                        {
                            "source_collection": collection_name,
                            "source_document_id": snapshot.id,
                            "row": row,
                            "archived_at": firestore.SERVER_TIMESTAMP,
                        },
                    )
                )
                delete_references.append(snapshot.reference)

    commit_rows(db, archive_rows)
    for reference in delete_references:
        reference.delete()


def commit_rows(db, rows: list[tuple[Any, dict[str, Any]]]) -> None:
    batch = db.batch()
    pending = 0
    for reference, record in rows:
        batch.set(reference, record, merge=True)
        pending += 1
        if pending == 450:
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()


def apply_import(db, plan: ImportPlan, target_balance: Decimal, replace_existing: bool) -> None:
    if plan.existing_ledger_count and not replace_existing:
        raise RuntimeError(
            f"Found {plan.existing_ledger_count} existing Blofin ledger rows. "
            "Re-run with --replace-existing to replace them with this CSV import."
        )

    if replace_existing:
        replace_existing_account_data(db, plan.uid)

    user = db.collection("users").document(plan.uid)
    user.set({"updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    user.collection("accounts").document(plan.account_id).set(
        {
            "name": ACCOUNT_NAME,
            "type": ACCOUNT_TYPE,
            "currency": ACCOUNT_CURRENCY,
            "starting_balance": decimal_to_float(plan.starting_balance),
            "created_at": ACCOUNT_CREATED_AT,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "source": "blofin_csv_import",
            "import_id": IMPORT_ID,
            "target_final_balance": decimal_to_float(target_balance),
        },
        merge=True,
    )

    import_reference = user.collection("imports").document(IMPORT_ID)
    import_reference.set(
        {
            "account": ACCOUNT_NAME,
            "target_final_balance": decimal_to_float(target_balance),
            "starting_balance": decimal_to_float(plan.starting_balance),
            "ledger_movement": decimal_to_float(plan.ledger_movement),
            "ledger_rows": len(plan.ledger_rows),
            "raw_rows": len(plan.raw_rows),
            "source_counts": plan.source_counts,
            "imported_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    ledger_references = [
        (user.collection(LEDGER_COLLECTION).document(entry_id), record) for entry_id, record in plan.ledger_rows
    ]
    raw_references = [
        (import_reference.collection("raw_rows").document(row_id), record) for row_id, record in plan.raw_rows
    ]
    commit_rows(db, ledger_references + raw_references)


def resolve_uid(email: str) -> str:
    get_firebase_app()
    return auth.get_user_by_email(email).uid


def main() -> None:
    parser = argparse.ArgumentParser(description="One-off Blofin CSV import into the Macroverse Firestore ledger.")
    parser.add_argument("--email", required=True, help="Firebase user email that owns the Blofin account.")
    parser.add_argument("--target-balance", required=True, help="Required final account balance.")
    parser.add_argument(
        "--csv-directory",
        type=Path,
        required=True,
        help="Directory containing one export for each supported Blofin CSV report type.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the import to Firestore. Without this, only prints a plan.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Delete existing Blofin ledger/import rows before writing this source-of-truth CSV import.",
    )
    args = parser.parse_args()

    target_balance = Decimal(args.target_balance)
    db = get_firestore_client()
    uid = resolve_uid(args.email)
    existing_count = existing_account_ledger_count(db, uid)
    plan = load_records(target_balance, uid, existing_count, args.csv_directory)

    print(f"Account: {ACCOUNT_NAME} ({plan.account_id})")
    print(f"Source counts: {plan.source_counts}")
    print(f"Ledger rows to write: {len(plan.ledger_rows)}")
    print(f"Raw CSV rows to store: {len(plan.raw_rows)}")
    print(f"Imported ledger movement: {money(plan.ledger_movement)}")
    print(f"Computed starting balance: {plan.starting_balance}")
    print(f"Expected final balance: {money(plan.starting_balance + plan.ledger_movement)}")
    print(f"Existing Blofin ledger rows: {existing_count}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to write the import.")
        return

    apply_import(db, plan, target_balance, args.replace_existing)
    print("Blofin import completed.")


if __name__ == "__main__":
    main()
