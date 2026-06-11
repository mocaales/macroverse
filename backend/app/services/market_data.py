import json
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from fastapi import HTTPException

from app.core.config import get_settings

FRED_SERIES = {
    "1 Month": "DGS1MO",
    "3 Month": "DGS3MO",
    "6 Month": "DGS6MO",
    "1 Year": "DGS1",
    "2 Year": "DGS2",
    "5 Year": "DGS5",
    "10 Year": "DGS10",
    "30 Year": "DGS30",
}


def fetch_btc_prices(start: datetime | None = None) -> pd.DataFrame:
    settings = get_settings()
    base_url = settings.coinmetrics_api_base_url.rstrip("/")
    parameters = {
        "assets": "btc",
        "metrics": "PriceUSD",
        "frequency": "1d",
        "start_time": (start or datetime(2011, 1, 1, tzinfo=UTC)).date().isoformat(),
        "page_size": 10_000,
    }
    rows = []
    while True:
        try:
            with urlopen(  # nosec B310
                f"{base_url}/timeseries/asset-metrics?{urlencode(parameters)}",
                timeout=30,
            ) as response:
                payload = json.load(response)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Bitcoin market data is unavailable.") from exc
        rows.extend(payload.get("data", []))
        next_page_token = payload.get("next_page_token")
        if not next_page_token:
            break
        parameters["next_page_token"] = next_page_token

    frame = pd.DataFrame(
        [{"date": row.get("time"), "value": row.get("PriceUSD")} for row in rows]
    )
    if frame.empty:
        return pd.DataFrame(columns=["date", "value"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["date", "value"]).drop_duplicates(subset=["date"], keep="last")
    return frame[["date", "value"]].sort_values("date")


def fetch_fred_series(series_id: str, start: datetime | None = None) -> pd.DataFrame:
    api_key = get_settings().fred_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="FRED_API_KEY is not configured.")
    parameters = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "asc",
    }
    if start:
        parameters["observation_start"] = start.date().isoformat()
    query = urlencode(parameters)
    try:
        with urlopen(f"https://api.stlouisfed.org/fred/series/observations?{query}", timeout=30) as response:  # nosec B310
            payload = json.load(response)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FRED market data is unavailable.") from exc
    rows = [
        {"date": row["date"], "value": float(row["value"])}
        for row in payload.get("observations", [])
        if row.get("value") not in (None, ".")
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["date", "value"])
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    return frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")


def fetch_cryptoquant_series(
    endpoint: str,
    value_key: str,
    *,
    start: datetime | None = None,
    window: str = "day",
) -> pd.DataFrame:
    access_token = get_settings().cryptoquant_access_token
    if not access_token:
        raise HTTPException(status_code=503, detail="CRYPTOQUANT_ACCESS_TOKEN is not configured.")
    parameters = {
        "window": window,
        "from": (start or datetime(2010, 1, 1, tzinfo=UTC)).date().isoformat(),
        "limit": 100_000,
        "format": "json",
    }
    request = Request(  # nosec B310
        f"https://api.cryptoquant.com/v1/{endpoint.strip('/')}?{urlencode(parameters)}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310
            payload = json.load(response)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="CryptoQuant market data is unavailable.") from exc
    if isinstance(payload.get("result"), dict):
        items = payload["result"].get("data", [])
    else:
        items = payload.get("data", payload.get("result", []))
    rows = []
    for item in items if isinstance(items, list) else []:
        date_value = (
            item.get("date")
            or item.get("datetime")
            or item.get("time")
            or item.get("timestamp")
            or item.get("t")
        )
        value = item.get(value_key)
        if date_value is not None and value is not None:
            rows.append({"date": date_value, "value": value})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["date", "value"])
    numeric_dates = pd.to_numeric(frame["date"], errors="coerce")
    frame["date"] = (
        pd.to_datetime(numeric_dates, unit="ms", errors="coerce", utc=True)
        .fillna(pd.to_datetime(numeric_dates, unit="s", errors="coerce", utc=True))
        .fillna(pd.to_datetime(frame["date"], errors="coerce", utc=True))
    )
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame.dropna().drop_duplicates(subset=["date"], keep="last").sort_values("date")


@lru_cache(maxsize=8)
def btc_prices() -> pd.DataFrame:
    return fetch_btc_prices()


@lru_cache(maxsize=32)
def fred_series(series_id: str) -> pd.DataFrame:
    return fetch_fred_series(series_id)
