import io
import pandas as pd
import streamlit as st

try:
    import requests
except Exception:  # pragma: no cover - fallback for environments without requests
    requests = None
    import urllib.request
    import json

try:
    import yfinance as yf
except Exception:  # pragma: no cover - fallback when yfinance isn't installed
    yf = None


FRED_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "date" not in df.columns or "price" not in df.columns:
        return pd.DataFrame(columns=["date", "price"])
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["date", "price"])
    frame = frame[frame["price"] > 0]
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return frame[["date", "price"]]


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_cryptoquant_series(
    endpoint: str,
    value_keys: tuple[str, ...],
    api_key: str,
    window: str = "day",
    start_date: str = "20100101",
    limit: int = 100000,
) -> pd.DataFrame:
    """
    Generic CryptoQuant series fetcher.
    Returns columns: date, value
    """
    if requests is None or not api_key:
        return pd.DataFrame(columns=["date", "value"])

    endpoint = endpoint.strip("/")
    url = f"https://api.cryptoquant.com/v1/{endpoint}"

    start_compact = start_date
    start_iso = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}" if len(start_date) == 8 else start_date
    param_variants = [
        {"window": window, "from": start_compact, "limit": int(limit), "format": "json"},
        {"window": window, "from": start_iso, "limit": int(limit), "format": "json"},
        {"from": start_iso, "limit": int(limit), "format": "json"},
        {"start": start_iso, "limit": int(limit), "format": "json"},
    ]
    header_variants = [
        {"Authorization": f"Bearer {api_key}"},
        {"X-API-KEY": api_key},
        {"Authorization": api_key},
        {},
    ]

    def _extract_rows(payload):
        items = []
        if isinstance(payload, dict):
            if isinstance(payload.get("result"), dict) and isinstance(payload["result"].get("data"), list):
                items = payload["result"]["data"]
            elif isinstance(payload.get("data"), list):
                items = payload["data"]
            elif isinstance(payload.get("result"), list):
                items = payload["result"]
        elif isinstance(payload, list):
            items = payload

        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            date_val = (
                item.get("date")
                or item.get("datetime")
                or item.get("time")
                or item.get("timestamp")
                or item.get("t")
            )
            if date_val is None:
                continue
            metric_val = None
            for key in value_keys:
                if key in item:
                    metric_val = item.get(key)
                    if metric_val is not None:
                        break
            if metric_val is None:
                for k, v in item.items():
                    if k in {"date", "datetime", "time", "timestamp", "t"}:
                        continue
                    if isinstance(v, (int, float)):
                        metric_val = v
                        break
            if metric_val is None:
                continue
            rows.append({"date": date_val, "value": metric_val})
        return rows

    for headers in header_variants:
        for params in param_variants:
            req_params = params.copy()
            if not headers:
                req_params["api_key"] = api_key
            try:
                resp = requests.get(url, headers=headers, params=req_params, timeout=30)
                if resp.status_code != 200:
                    continue
                payload = resp.json()
            except Exception:
                continue

            rows = _extract_rows(payload)
            if not rows:
                continue

            df = pd.DataFrame(rows)
            numeric_date = pd.to_numeric(df["date"], errors="coerce")
            as_ms = pd.to_datetime(numeric_date, unit="ms", errors="coerce")
            as_s = pd.to_datetime(numeric_date, unit="s", errors="coerce")
            as_str = pd.to_datetime(df["date"], errors="coerce")
            df["date"] = as_ms.fillna(as_s).fillna(as_str)
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date", "value"])
            df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
            if not df.empty:
                return df[["date", "value"]].reset_index(drop=True)

    return pd.DataFrame(columns=["date", "value"])


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_yfinance_prices(ticker: str) -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame(columns=["date", "price"])
    try:
        data = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    if data is None or data.empty:
        return pd.DataFrame(columns=["date", "price"])
    try:
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"].iloc[:, 0]
        else:
            close = data["Close"]
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    df = close.reset_index()
    df = df.rename(columns={"Date": "date", "Close": "price"})
    if "price" not in df.columns and close.name in df.columns:
        df = df.rename(columns={close.name: "price"})
    if "price" not in df.columns and len(df.columns) >= 2:
        df = df.rename(columns={df.columns[1]: "price"})
    return _normalize_price_frame(df)


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_cryptocompare_prices(symbol: str) -> pd.DataFrame:
    if requests is None:
        return pd.DataFrame(columns=["date", "price"])
    url = "https://min-api.cryptocompare.com/data/v2/histoday"
    to_ts = int(pd.Timestamp.utcnow().timestamp())
    chunks = []
    for _ in range(12):
        params = {"fsym": symbol.upper(), "tsym": "USD", "limit": 2000, "toTs": to_ts}
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            break
        data_block = payload.get("Data", {})
        points = data_block.get("Data", []) if isinstance(data_block, dict) else []
        if not points:
            break
        chunk = pd.DataFrame(points)
        if "time" not in chunk.columns or "close" not in chunk.columns:
            break
        chunk["date"] = pd.to_datetime(chunk["time"], unit="s")
        chunk["price"] = pd.to_numeric(chunk["close"], errors="coerce")
        chunks.append(chunk[["date", "price"]])
        oldest_ts = int(chunk["time"].min())
        next_to_ts = oldest_ts - 86400
        if next_to_ts >= to_ts:
            break
        to_ts = next_to_ts
    if not chunks:
        return pd.DataFrame(columns=["date", "price"])
    return _normalize_price_frame(pd.concat(chunks, ignore_index=True))


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_coingecko_prices(coin_id: str) -> pd.DataFrame:
    if requests is None:
        return pd.DataFrame(columns=["date", "price"])
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "max", "interval": "daily"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    prices = payload.get("prices", [])
    if not prices:
        return pd.DataFrame(columns=["date", "price"])
    df = pd.DataFrame(prices, columns=["ts_ms", "price"])
    df["date"] = pd.to_datetime(df["ts_ms"], unit="ms")
    return _normalize_price_frame(df[["date", "price"]])


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_stooq_prices(symbol: str) -> pd.DataFrame:
    if requests is None:
        return pd.DataFrame(columns=["date", "price"])
    url = "https://stooq.com/q/d/l/"
    params = {"s": symbol.lower(), "i": "d"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        raw = pd.read_csv(io.StringIO(resp.text))
    except Exception:
        return pd.DataFrame(columns=["date", "price"])
    if raw.empty:
        return pd.DataFrame(columns=["date", "price"])
    col_map = {str(c).strip().lower(): c for c in raw.columns}
    date_col = col_map.get("date")
    close_col = col_map.get("close")
    if date_col is None or close_col is None:
        return pd.DataFrame(columns=["date", "price"])
    df = raw[[date_col, close_col]].rename(columns={date_col: "date", close_col: "price"})
    return _normalize_price_frame(df)


def _combine_price_sources(sources: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [_normalize_price_frame(s) for s in sources if s is not None and not s.empty]
    if not valid:
        return pd.DataFrame(columns=["date", "price"])
    combined = valid[0].set_index("date").sort_index()
    for frame in valid[1:]:
        combined = combined.combine_first(frame.set_index("date").sort_index())
    merged = combined.reset_index()
    return _normalize_price_frame(merged)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_fred_series(series_id, api_key):
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}&file_type=json"
    )
    if requests:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    else:
        with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    obs = data.get("observations", [])
    rows = []
    for o in obs:
        val = o.get("value")
        if val in (None, ".", ""):
            continue
        rows.append({"date": o.get("date"), "value": float(val)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_sp500_overlay():
    if yf is None:
        return pd.DataFrame()
    data = yf.download("^GSPC", period="max", interval="1d", auto_adjust=True, progress=False)
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
        close = close.iloc[:, 0]
    else:
        close = data["Close"]
    df = close.reset_index()
    df = df.rename(columns={"Date": "date"})
    if "Close" in df.columns:
        df = df.rename(columns={"Close": "overlay"})
    elif close.name in df.columns:
        df = df.rename(columns={close.name: "overlay"})
    elif len(df.columns) >= 2:
        df = df.rename(columns={df.columns[1]: "overlay"})
    if "overlay" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_btc_blockchain():
    if requests is None:
        return pd.DataFrame()
    url = "https://api.blockchain.info/charts/market-price"
    params = {"timespan": "all", "format": "json"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return pd.DataFrame()
    values = payload.get("values", [])
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values)
    if "x" not in df.columns or "y" not in df.columns:
        return pd.DataFrame()
    df = df.rename(columns={"x": "ts", "y": "price"})
    df["date"] = pd.to_datetime(df["ts"], unit="s")
    df = df.drop(columns=["ts"]).sort_values("date")
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_btc_coindesk(start="2010-07-17"):
    if requests is None:
        return pd.DataFrame()
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    url = "https://api.coindesk.com/v1/bpi/historical/close.json"
    params = {"start": start, "end": end}
    try:
        resp = requests.get(url, params=params, timeout=30)
    except Exception:
        return pd.DataFrame()
    if resp.status_code != 200:
        return pd.DataFrame()
    try:
        payload = resp.json()
    except Exception:
        return pd.DataFrame()
    bpi = payload.get("bpi", {})
    if not bpi:
        return pd.DataFrame()
    df = pd.DataFrame(sorted(bpi.items()), columns=["date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_btc_prices():
    # Blend multiple providers for resilience and deeper history.
    yfin = _fetch_yfinance_prices("BTC-USD")
    cryptocompare = _fetch_cryptocompare_prices("BTC")
    coingecko = _fetch_coingecko_prices("bitcoin")
    blockchain = _fetch_btc_blockchain()
    if blockchain.empty:
        blockchain = _fetch_btc_coindesk()

    combined = _combine_price_sources([coingecko, cryptocompare, yfin, blockchain])
    return combined.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_eth_prices():
    # ETH first traded in 2015. Combine providers to maximize history and resilience.
    yfin = _fetch_yfinance_prices("ETH-USD")
    cryptocompare = _fetch_cryptocompare_prices("ETH")
    coingecko = _fetch_coingecko_prices("ethereum")
    combined = _combine_price_sources([coingecko, cryptocompare, yfin])
    if combined.empty:
        return combined
    combined = combined[combined["date"] >= pd.Timestamp("2015-01-01")]
    return combined.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_yfinance_symbol_prices(symbol: str):
    return _fetch_yfinance_prices(symbol)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_gold_prices():
    # Use multiple providers and merge for maximum practical history.
    # GC=F usually provides the deepest gold series in Yahoo.
    gc_futures = _fetch_yfinance_prices("GC=F")
    xauusd_fx = _fetch_yfinance_prices("XAUUSD=X")
    gld_etf = _fetch_yfinance_prices("GLD")
    stooq_xau = _fetch_stooq_prices("xauusd")
    combined = _combine_price_sources([gc_futures, xauusd_fx, stooq_xau, gld_etf])
    return combined.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_silver_prices():
    # Blend silver sources for longer and more stable coverage.
    si_futures = _fetch_yfinance_prices("SI=F")
    xagusd_fx = _fetch_yfinance_prices("XAGUSD=X")
    slv_etf = _fetch_yfinance_prices("SLV")
    stooq_xag = _fetch_stooq_prices("xagusd")
    combined = _combine_price_sources([si_futures, xagusd_fx, stooq_xag, slv_etf])
    return combined.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_spx500_prices():
    return _fetch_yfinance_prices("^GSPC")


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_qqq_prices():
    return _fetch_yfinance_prices("QQQ")


def _merge_series(primary, fallback):
    if primary.empty:
        return fallback
    if fallback.empty:
        return primary
    p = primary.set_index("date").sort_index()
    f = fallback.set_index("date").sort_index()
    combined = p.combine_first(f)
    return combined.reset_index()


def _to_daily(df):
    if df.empty:
        return df
    df = df.set_index("date").sort_index()
    full_range = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full_range).ffill()
    df.index.name = "date"
    return df.reset_index()
