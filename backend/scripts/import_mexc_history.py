from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from firebase_admin import auth, firestore
from pypdf import PdfReader

from app.core.firebase import get_firebase_app, get_firestore_client
from app.repositories.portfolio import (
    LEDGER_COLLECTION,
    LEGACY_TRADE_COLLECTION,
    _account_id,
)

ACCOUNT_NAME = "MEXC"
ACCOUNT_TYPE = "Trading Account"
ACCOUNT_CURRENCY = "USD"
IMPORT_ID = "mexc_2025_2026"
REPORT_TIMEZONE = timezone(timedelta(hours=2))
ACCOUNT_CREATED_AT = datetime(2025, 6, 19, tzinfo=REPORT_TIMEZONE)
ROW_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(\S+)\s+(\S+)\s+([A-Z_]+)\s+(Inflow|Outflow)\s+(-?[0-9]+(?:\.[0-9]+)?)\s*$"
)


@dataclass(frozen=True)
class FundFlowRow:
    occurred_at: datetime
    pair: str
    crypto: str
    fund_type: str
    flow_type: str
    amount: Decimal


@dataclass(frozen=True)
class ImportPlan:
    uid: str
    starting_balance: Decimal
    ledger_movement: Decimal
    rows: list[FundFlowRow]
    existing_ledger_count: int


def decimal_to_float(value: Decimal) -> float:
    return float(stored_decimal(value))


def stored_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def document_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def parse_report(path: Path) -> list[FundFlowRow]:
    if not path.exists():
        raise FileNotFoundError(f"MEXC report not found: {path}")

    rows = []
    unmatched_data_rows = []
    for page in PdfReader(path).pages:
        text = page.extract_text(extraction_mode="layout") or ""
        for line in text.splitlines():
            stripped = line.strip()
            match = ROW_PATTERN.match(stripped)
            if match:
                occurred_at, pair, crypto, fund_type, flow_type, amount = match.groups()
                parsed_amount = Decimal(amount)
                if (flow_type == "Inflow" and parsed_amount < 0) or (flow_type == "Outflow" and parsed_amount > 0):
                    raise ValueError(f"Inconsistent flow direction in report row: {stripped}")
                rows.append(
                    FundFlowRow(
                        occurred_at=datetime.strptime(occurred_at, "%Y-%m-%d %H:%M:%S").replace(
                            tzinfo=REPORT_TIMEZONE
                        ),
                        pair=pair,
                        crypto=crypto,
                        fund_type=fund_type,
                        flow_type=flow_type,
                        amount=parsed_amount,
                    )
                )
            elif re.match(r"^\d{4}-\d{2}-\d{2}", stripped):
                unmatched_data_rows.append(stripped)

    if unmatched_data_rows:
        raise ValueError(f"Could not parse {len(unmatched_data_rows)} report rows.")
    if not rows:
        raise ValueError("The MEXC report contains no fund-flow rows.")
    return rows


def ledger_record(row: FundFlowRow, row_number: int) -> tuple[str, dict[str, Any]]:
    entry_id = document_id(
        "mexc_fund_flow",
        row_number,
        row.occurred_at.isoformat(),
        row.pair,
        row.fund_type,
        row.amount,
    )
    action = "Trade" if row.fund_type == "CLOSE_POSITION" else ("Deposit" if row.amount >= 0 else "Withdraw")
    category = {
        "FEE": "Fees",
        "TRANSFER": "Transfer",
    }.get(row.fund_type, "Other")
    labels = {
        "CLOSE_POSITION": "Position closed",
        "FEE": "Trading fee",
        "FUNDING": "Funding payment",
        "TRANSFER": "Futures account transfer",
    }
    return entry_id, {
        "account": ACCOUNT_NAME,
        "trade_time": row.occurred_at,
        "action": action,
        "type": None,
        "symbol": row.pair if row.pair != "--" else row.crypto,
        "pnl": decimal_to_float(row.amount),
        "description": f"MEXC {labels.get(row.fund_type, row.fund_type.replace('_', ' ').title())}",
        "notes": f"Fund type: {row.fund_type}. Flow: {row.flow_type}. Crypto: {row.crypto}.",
        "category": category,
        "source": "mexc_futures_fund_flow",
        "source_row": row_number,
        "import_id": IMPORT_ID,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


def raw_record(row: FundFlowRow, row_number: int) -> tuple[str, dict[str, Any]]:
    row_id = document_id("mexc_raw", row_number, row.occurred_at.isoformat(), row.pair, row.fund_type, row.amount)
    return row_id, {
        "account": ACCOUNT_NAME,
        "source": "mexc_futures_fund_flow",
        "source_row": row_number,
        "occurred_at": row.occurred_at,
        "pair": row.pair,
        "crypto": row.crypto,
        "fund_type": row.fund_type,
        "flow_type": row.flow_type,
        "amount": decimal_to_float(row.amount),
        "import_id": IMPORT_ID,
        "imported_at": firestore.SERVER_TIMESTAMP,
    }


def existing_account_ledger_count(db, uid: str) -> int:
    user = db.collection("users").document(uid)
    return sum(
        1
        for collection_name in (LEDGER_COLLECTION, LEGACY_TRADE_COLLECTION)
        for snapshot in user.collection(collection_name).stream()
        if (snapshot.to_dict() or {}).get("account") == ACCOUNT_NAME
    )


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


def replace_existing_account_data(db, uid: str) -> None:
    user = db.collection("users").document(uid)
    import_reference = user.collection("imports").document(IMPORT_ID)
    db.recursive_delete(import_reference)
    archive_rows = []
    delete_references = []
    for collection_name in (LEDGER_COLLECTION, LEGACY_TRADE_COLLECTION):
        for snapshot in user.collection(collection_name).stream():
            row = snapshot.to_dict() or {}
            if row.get("account") != ACCOUNT_NAME:
                continue
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


def apply_import(db, plan: ImportPlan, target_balance: Decimal, replace_existing: bool) -> None:
    if plan.existing_ledger_count and not replace_existing:
        raise RuntimeError(
            f"Found {plan.existing_ledger_count} existing MEXC ledger rows. "
            "Re-run with --replace-existing to archive and replace them."
        )
    if replace_existing:
        replace_existing_account_data(db, plan.uid)

    user = db.collection("users").document(plan.uid)
    user.set({"updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    user.collection("accounts").document(_account_id(ACCOUNT_NAME)).set(
        {
            "name": ACCOUNT_NAME,
            "type": ACCOUNT_TYPE,
            "currency": ACCOUNT_CURRENCY,
            "starting_balance": decimal_to_float(plan.starting_balance),
            "created_at": ACCOUNT_CREATED_AT,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "source": "mexc_pdf_import",
            "import_id": IMPORT_ID,
            "target_final_balance": decimal_to_float(target_balance),
        },
        merge=True,
    )

    import_reference = user.collection("imports").document(IMPORT_ID)
    counts = Counter(row.fund_type for row in plan.rows)
    import_reference.set(
        {
            "account": ACCOUNT_NAME,
            "target_final_balance": decimal_to_float(target_balance),
            "starting_balance": decimal_to_float(plan.starting_balance),
            "ledger_movement": decimal_to_float(plan.ledger_movement),
            "row_count": len(plan.rows),
            "fund_type_counts": dict(counts),
            "imported_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    ledger_rows = [
        (user.collection(LEDGER_COLLECTION).document(entry_id), record)
        for entry_id, record in (ledger_record(row, index) for index, row in enumerate(plan.rows, start=1))
    ]
    raw_rows = [
        (import_reference.collection("raw_rows").document(row_id), record)
        for row_id, record in (raw_record(row, index) for index, row in enumerate(plan.rows, start=1))
    ]
    commit_rows(db, ledger_rows + raw_rows)


def resolve_uid(email: str) -> str:
    get_firebase_app()
    return auth.get_user_by_email(email).uid


def main() -> None:
    parser = argparse.ArgumentParser(description="One-off MEXC futures fund-flow import into Macroverse Firestore.")
    parser.add_argument("--email", required=True, help="Firebase user email that owns the MEXC account.")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to the MEXC Futures Fund Flow PDF.")
    parser.add_argument("--target-balance", required=True, help="Required final balance.")
    parser.add_argument("--apply", action="store_true", help="Write the import to Firestore.")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Archive and replace existing MEXC ledger/import rows.",
    )
    args = parser.parse_args()

    rows = parse_report(args.pdf)
    target_balance = Decimal(args.target_balance)
    ledger_movement = sum((stored_decimal(row.amount) for row in rows), Decimal())
    starting_balance = target_balance - ledger_movement
    db = get_firestore_client()
    uid = resolve_uid(args.email)
    plan = ImportPlan(
        uid=uid,
        starting_balance=starting_balance,
        ledger_movement=ledger_movement,
        rows=rows,
        existing_ledger_count=existing_account_ledger_count(db, uid),
    )

    print(f"Account: {ACCOUNT_NAME}")
    print(f"Report rows: {len(rows)}")
    print(f"Fund types: {dict(Counter(row.fund_type for row in rows))}")
    print(f"Ledger movement: {ledger_movement}")
    print(f"Computed starting balance: {starting_balance}")
    print(f"Expected final balance: {starting_balance + ledger_movement}")
    print(f"Existing MEXC ledger rows: {plan.existing_ledger_count}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to write the import.")
        return
    apply_import(db, plan, target_balance, args.replace_existing)
    print("MEXC import completed.")


if __name__ == "__main__":
    main()
