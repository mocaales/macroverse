from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from tracker.charts.data import fetch_btc_prices


MARKET_PRICE_COLLECTION = "market_price_daily"


def ensure_market_price_indexes(db) -> None:
    db[MARKET_PRICE_COLLECTION].create_index(
        [("asset", 1), ("date", 1)],
        unique=True,
        name="asset_date_unique",
    )
    db[MARKET_PRICE_COLLECTION].create_index(
        [("asset", 1), ("updated_at", -1)],
        name="asset_updated_at_idx",
    )


def build_market_price_records(
    prices_df: pd.DataFrame,
    *,
    asset: str,
    currency: str = "USD",
    timeframe: str = "1d",
    source: str = "free-public",
) -> list[dict]:
    if prices_df.empty:
        return []

    frame = prices_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["date", "price"])
    frame = frame[frame["price"] > 0]
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    now = datetime.now(timezone.utc)
    records = []
    for row in frame.itertuples(index=False):
        records.append(
            {
                "asset": asset.upper(),
                "currency": currency.upper(),
                "timeframe": timeframe,
                "date": row.date.to_pydatetime(),
                "close": float(row.price),
                "source": source,
                "updated_at": now,
            }
        )
    return records


def upsert_market_price_records(db, records: list[dict]) -> dict:
    ensure_market_price_indexes(db)
    collection = db[MARKET_PRICE_COLLECTION]

    inserted = 0
    updated = 0
    for record in records:
        selector = {"asset": record["asset"], "date": record["date"]}
        existing = collection.find_one(selector, {"_id": 1, "close": 1, "source": 1})
        collection.update_one(selector, {"$set": record}, upsert=True)
        if existing is None:
            inserted += 1
        else:
            updated += 1

    return {
        "count": len(records),
        "inserted": inserted,
        "updated": updated,
    }


def import_btc_daily_history(db) -> dict:
    prices_df = fetch_btc_prices()
    records = build_market_price_records(
        prices_df,
        asset="BTC",
        currency="USD",
        timeframe="1d",
        source="free-public",
    )
    result = upsert_market_price_records(db, records)
    if records:
        result["start_date"] = records[0]["date"].date().isoformat()
        result["end_date"] = records[-1]["date"].date().isoformat()
    else:
        result["start_date"] = None
        result["end_date"] = None
    return result
