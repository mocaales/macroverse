from __future__ import annotations

import argparse
from dataclasses import dataclass

from app.core.firebase import get_firestore_client
from app.models.portfolio import normalize_account_type
from app.repositories.portfolio import PortfolioRepository


@dataclass(frozen=True)
class AccountRemoval:
    uid: str
    account_name: str
    account_type: str


def find_non_trading_accounts(db) -> list[AccountRemoval]:
    removals = []
    for user_snapshot in db.collection("users").stream():
        accounts = user_snapshot.reference.collection("accounts")
        for account_snapshot in accounts.stream():
            row = account_snapshot.to_dict() or {}
            account_type = normalize_account_type(str(row.get("type", "")))
            if account_type == "Trading Account":
                continue
            removals.append(
                AccountRemoval(
                    uid=user_snapshot.id,
                    account_name=str(row.get("name") or account_snapshot.id),
                    account_type=account_type or "Unknown",
                )
            )
    return sorted(removals, key=lambda item: (item.uid, item.account_name.casefold()))


def apply_removals(repository: PortfolioRepository, removals: list[AccountRemoval]) -> int:
    deleted = 0
    for removal in removals:
        if repository.delete_account(removal.uid, removal.account_name):
            deleted += 1
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove every non-trading account and its related Firestore portfolio data."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletions. Without this flag, only print the planned removals.",
    )
    args = parser.parse_args()

    db = get_firestore_client()
    repository = PortfolioRepository(db)
    removals = find_non_trading_accounts(db)

    print(f"Non-trading accounts found: {len(removals)}")
    for removal in removals:
        print(f"- user={removal.uid} account={removal.account_name!r} type={removal.account_type!r}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to delete these accounts and related data.")
        return

    deleted = apply_removals(repository, removals)
    print(f"Deleted non-trading accounts: {deleted}")


if __name__ == "__main__":
    main()
