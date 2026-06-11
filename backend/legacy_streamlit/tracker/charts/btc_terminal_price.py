"""
Bitcoin Terminal, Balanced & Realized Price
============================================
Single-file implementation:
  - YFinance BTC price history (BTC-USD daily)
  - Checkonchain Onchain Originals model lines (Realised, Balanced)
  - Streamlit chart rendering (log view + ratio view)

Formulas:
  - RealizedPrice(t)    = Checkonchain published Realised Price
  - BalancedPrice(t)    = Checkonchain published Balanced Price
  - TransferredPrice(t) = RealizedPrice(t) - BalancedPrice(t)
  - TerminalPrice(t)    = 21 × TransferredPrice(t)
  - Model lines are masked before 2016-01-01

Engineering constraints (spec §6):
  - float64 throughout
  - NaN when supply ≤ 0 or any metric ≤ 0 (log-scale safety)
  - All datetime handling via _to_utc_naive() to prevent tz-mixing errors

Data sources:
  - Price + Models: Checkonchain Onchain Originals public chart payload
    (yfinance price fallback)
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

TERMINAL_MULTIPLIER: float = 21.0
_REQUEST_TIMEOUT = 20
_LARGE_TIMEOUT   = 60
_HISTORY_START   = "2010-07-17"

_CHART_COLORS = {
    "price":          "#4ea3ff",
    "terminal_price": "#f87171",
    "realized_price": "#22c55e",
    "balanced_price": "#f59e0b",
    "ratio_ref":      "rgba(255,255,255,0.35)",
}
_CHART_HEIGHT = 720
_CM_ASSET_METRICS_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
_CHECKONCHAIN_ONCHAIN_ORIGINALS_URL = (
    "https://charts.checkonchain.com/btconchain/pricing/"
    "pricing_onchainoriginals/pricing_onchainoriginals_light.html"
)
_CHECKONCHAIN_MODEL_TRACE_MAP = {
    "Price": "price_ref",
    "Realised Price": "realized_price",
    "Balanced Price": "balanced_price",
}
_CM_ONCHAIN_METRIC_CANDIDATES: dict[str, tuple[str, ...]] = {
    "realized_cap": ("CapRealUSD",),
    "supply_total": ("SplyCur",),
    # Prefer unadjusted coin-days-destroyed; adjusted variant is fallback.
    "cdd": (
        "TxTfrValDayDst",
        "TxTfrValAdjDayDst",
        "CDD",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Timezone safety helper
# ─────────────────────────────────────────────────────────────────────────────

def _to_utc_naive(series: pd.Series) -> pd.Series:
    """
    Convert any datetime Series to tz-naive UTC (datetime64[ns], no tzinfo).

    Handles all cases:
      - Already tz-naive               → pass through
      - tz-aware (any zone, incl. UTC) → convert to UTC then strip tz
      - Mixed tz-aware/naive objects   → parse with utc=True then strip
      - Strings (ISO, epoch strings)   → parse with utc=True then strip

    This is the single authoritative datetime normalisation point; call it
    whenever a date column is parsed from an external source to prevent
    "Cannot mix tz-aware with tz-naive" errors during pd.concat / merge.
    """
    if series.empty:
        return series

    # If already datetime64 with a timezone, convert to UTC and strip
    if hasattr(series.dtype, "tz") and series.dtype.tz is not None:
        return series.dt.tz_convert("UTC").dt.tz_localize(None)

    # If datetime64 without timezone — already naive, return as-is
    if pd.api.types.is_datetime64_dtype(series):
        return series

    # Object/string column — parse with utc=True to unify any mixed tz info,
    # then strip to tz-naive. format='mixed' preserves heterogeneous string
    # formats (e.g., date-only + ISO8601 with offsets) on newer pandas.
    try:
        parsed = pd.to_datetime(series, utc=True, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(series, utc=True, errors="coerce")
    return parsed.dt.tz_localize(None)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MetricConfig:
    terminal_multiplier: float                   = TERMINAL_MULTIPLIER
    fallback_realized_geo_window: int            = 900
    fallback_realized_geo_weight: float          = 0.76
    fallback_realized_ema_span: int              = 620
    fallback_realized_momentum_alpha_up: float   = 0.075
    fallback_realized_momentum_alpha_down: float = 0.012
    fallback_transferred_ewm_span: int           = 95
    reliable_start_date: str                     = "2016-01-01"


@dataclass
class MetricResult:
    """
    Output from compute_metrics().

    df columns:
        price, realized_price, transferred_price, balanced_price, terminal_price
        (float64; NaN where undefined or non-positive)

    Ratio columns added by add_ratio_columns():
        ratio_price_terminal, ratio_price_realized, ratio_price_balanced
    """
    df: pd.DataFrame
    has_onchain: bool
    t0: Optional[pd.Timestamp] = None
    warnings: list[str] = field(default_factory=list)

    def add_ratio_columns(self) -> None:
        """In-place: Price / metric ratio columns (linear scale)."""
        for col, ratio_col in [
            ("terminal_price", "ratio_price_terminal"),
            ("realized_price", "ratio_price_realized"),
            ("balanced_price", "ratio_price_balanced"),
        ]:
            denom = self.df[col].replace(0.0, np.nan)
            self.df[ratio_col] = (self.df["price"] / denom).astype("float64")


# ─────────────────────────────────────────────────────────────────────────────
# Metric computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(
    price: pd.Series,
    supply: pd.Series,
    realized_cap: Optional[pd.Series] = None,
    cdd: Optional[pd.Series] = None,
    price_for_onchain: Optional[pd.Series] = None,
    dates: Optional[pd.Series] = None,
    config: MetricConfig = MetricConfig(),
) -> MetricResult:
    """
    Compute valuation metrics using exact on-chain formulas where available:
      RealizedPrice    = RealizedCap / Supply
      TransferredPrice = cumulative(CDD * Price) / cumulative(CDD)
      BalancedPrice    = RealizedPrice - TransferredPrice
      TerminalPrice    = 21 * TransferredPrice

    Missing on-chain segments are filled with a smooth local fallback model to
    keep chart continuity.
    Inputs must be pre-sorted ascending, de-duplicated, reset index 0..N-1.
    """
    n = len(price)
    warnings: list[str] = []

    for name, s in [
        ("supply", supply),
        ("realized_cap", realized_cap),
        ("cdd", cdd),
        ("price_for_onchain", price_for_onchain),
        ("dates", dates),
    ]:
        if s is not None and len(s) != n:
            raise ValueError(f"Length mismatch: {name}={len(s)} vs price={n}")

    p_arr = np.asarray(price, dtype=np.float64)  # chart/display price
    p_on_arr = (np.asarray(price_for_onchain, dtype=np.float64)
                if price_for_onchain is not None else p_arr)  # on-chain valuation price
    s_arr = np.asarray(supply, dtype=np.float64)
    if dates is not None:
        dt = _to_utc_naive(dates).dt.normalize()
        genesis = pd.Timestamp("2009-01-03")
        age_days = ((dt - genesis).dt.days + 1).to_numpy(dtype=np.float64)
    else:
        age_days = np.arange(1, n + 1, dtype=np.float64)
    age_days = np.where(np.isfinite(age_days) & (age_days > 0), age_days, np.nan)

    valid_ps = (
        np.isfinite(p_on_arr) & (p_on_arr > 0) &
        np.isfinite(s_arr) & (s_arr > 0)
    )
    if not valid_ps.any():
        return MetricResult(
            df=pd.DataFrame(columns=["price", "realized_price", "transferred_price",
                                     "balanced_price", "terminal_price"]),
            has_onchain=False,
            warnings=["No valid rows in intersection of price and supply."],
        )

    has_realized = realized_cap is not None and not pd.isna(realized_cap).all()
    has_cdd = cdd is not None and not pd.isna(cdd).all()
    has_onchain = has_realized and has_cdd
    both_missing = (not has_realized) and (not has_cdd)

    realized_arr = np.full(n, np.nan, dtype=np.float64)
    transferred_arr = np.full(n, np.nan, dtype=np.float64)

    # Exact realized price from realized cap / supply.
    if has_realized:
        rc_arr = np.asarray(realized_cap, dtype=np.float64)
        valid_rc = valid_ps & np.isfinite(rc_arr) & (rc_arr > 0)
        realized_arr[valid_rc] = rc_arr[valid_rc] / s_arr[valid_rc]
    elif not both_missing:
        warnings.append("realized_cap missing; using fallback estimate for realized price.")

    # Exact transferred price from cumulative CDD-weighted average price.
    if has_cdd:
        cdd_arr = np.asarray(cdd, dtype=np.float64)
        cdd_pos = np.where(np.isfinite(cdd_arr) & (cdd_arr > 0), cdd_arr, 0.0)
        vdd_with_price = cdd_pos * np.where(np.isfinite(p_on_arr) & (p_on_arr > 0), p_on_arr, 0.0)
        vdd_direct = cdd_pos.copy()

        cum_with_price = np.cumsum(vdd_with_price, dtype=np.float64)
        cum_direct = np.cumsum(vdd_direct, dtype=np.float64)
        denom = age_days * s_arr

        tr_with_price = np.full(n, np.nan, dtype=np.float64)
        tr_direct = np.full(n, np.nan, dtype=np.float64)
        valid_denom = np.isfinite(denom) & (denom > 0)
        valid_wp = valid_denom & np.isfinite(cum_with_price) & (cum_with_price > 0)
        valid_dr = valid_denom & np.isfinite(cum_direct) & (cum_direct > 0)
        tr_with_price[valid_wp] = cum_with_price[valid_wp] / denom[valid_wp]
        tr_direct[valid_dr] = cum_direct[valid_dr] / denom[valid_dr]

        # Choose the domain that gives plausible scale (prevents price double-counting).
        def _score(candidate: np.ndarray) -> float:
            valid = np.isfinite(candidate)
            if not valid.any():
                return np.inf
            idx = int(np.where(valid)[0][-1])
            if has_realized and np.isfinite(realized_arr[idx]) and realized_arr[idx] > 0:
                ratio = float(candidate[idx] / realized_arr[idx])
                target = 0.25  # historically transferred as fraction of realized price
            elif np.isfinite(p_on_arr[idx]) and p_on_arr[idx] > 0:
                ratio = float(candidate[idx] / p_on_arr[idx])
                target = 0.22  # historically transferred as fraction of market price
            else:
                return np.inf
            if not np.isfinite(ratio) or ratio <= 0:
                return np.inf
            return abs(np.log(ratio / target))

        use_with_price = _score(tr_with_price) <= _score(tr_direct)
        transferred_arr = tr_with_price if use_with_price else tr_direct
        warnings.append(
            "Transferred Price domain: "
            + ("CDD×Price (coin-days input detected)." if use_with_price
               else "CDD direct (value-days input detected).")
        )
    elif not both_missing:
        warnings.append("CDD missing; using fallback estimate for transferred price.")

    # Fallback model to fill missing segments only.
    missing_realized = ~np.isfinite(realized_arr)
    missing_transferred = ~np.isfinite(transferred_arr)
    if missing_realized.any() or missing_transferred.any():
        p_s   = pd.Series(p_arr)
        log_p = np.log(p_s.clip(lower=1e-10))

        geo  = np.exp(log_p.rolling(window=config.fallback_realized_geo_window, min_periods=45).mean())
        ema  = p_s.ewm(span=config.fallback_realized_ema_span, adjust=False).mean()
        w    = config.fallback_realized_geo_weight
        seed = (w * geo + (1.0 - w) * ema).combine_first(
            np.exp(log_p.expanding(min_periods=2).mean())
        ).ffill().bfill().to_numpy(dtype=np.float64)

        realized_fb = seed.copy()
        for i in range(1, n):
            prev  = realized_fb[i - 1]
            cur   = realized_fb[i]
            if not np.isfinite(cur):
                cur = prev
            alpha = (config.fallback_realized_momentum_alpha_up
                     if cur > prev else config.fallback_realized_momentum_alpha_down)
            realized_fb[i] = prev + alpha * (cur - prev)

        age   = np.arange(1, n + 1, dtype=np.float64)
        ratio = np.interp(age,
                          [1.0, 365*2, 365*6, 365*11, 365*17],
                          [0.90, 0.72,  0.50,  0.36,  0.28])
        ma365 = p_s.rolling(window=365, min_periods=30).mean()
        mom   = (p_s / ma365).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        ratio = np.clip(ratio * (0.95 + 0.08 * mom.clip(0.8, 1.3).to_numpy()), 0.20, 0.95)
        rp_s  = pd.Series(realized_fb)
        transferred_fb = pd.Series(realized_fb * ratio).ewm(
            span=config.fallback_transferred_ewm_span, adjust=False
        ).mean().clip(lower=(rp_s * 0.20), upper=(rp_s * 0.96)).to_numpy(dtype=np.float64)

        realized_arr[missing_realized] = realized_fb[missing_realized]
        transferred_arr[missing_transferred] = transferred_fb[missing_transferred]
        if both_missing:
            warnings.append("On-chain realized cap and CDD missing; using fallback valuation model.")
        elif not has_onchain:
            warnings.append("On-chain inputs unavailable; using fallback valuation model.")
        else:
            warnings.append("On-chain coverage has gaps; fallback fills missing segments.")

    terminal_arr = np.array(config.terminal_multiplier * transferred_arr, dtype=np.float64)
    balanced_arr = np.array(realized_arr - transferred_arr, dtype=np.float64)

    if dates is not None:
        dt = _to_utc_naive(dates).dt.normalize()
        model_start = pd.Timestamp(config.reliable_start_date)
        reliable_mask = (dt >= model_start).to_numpy(dtype=bool)
        realized_arr[~reliable_mask] = np.nan
        transferred_arr[~reliable_mask] = np.nan
        balanced_arr[~reliable_mask] = np.nan
        terminal_arr[~reliable_mask] = np.nan

    for arr in (realized_arr, transferred_arr, balanced_arr, terminal_arr):
        arr[~(np.isfinite(arr) & (arr > 0))] = np.nan

    out_df = pd.DataFrame({
        "price":             p_arr,
        "realized_price":    realized_arr,
        "transferred_price": transferred_arr,
        "balanced_price":    balanced_arr,
        "terminal_price":    terminal_arr,
    }, dtype=np.float64)

    return MetricResult(df=out_df, has_onchain=has_onchain, warnings=list(dict.fromkeys(warnings)))


def estimate_supply_from_schedule(dates: pd.Series) -> pd.Series:
    """
    Deterministic BTC issuance schedule. 144 blocks/day, halving every 210,000
    blocks, genesis 2009-01-03. Caps at 21,000,000. O(N×40) ≈ O(N).
    """
    genesis          = pd.Timestamp("2009-01-03")
    BLOCKS_PER_DAY   = 144.0
    BLOCKS_PER_EPOCH = 210_000.0
    MAX_SUPPLY       = 21_000_000.0

    dates_ts = _to_utc_naive(dates)
    out = np.empty(len(dates_ts), dtype=np.float64)
    for idx, dt in enumerate(dates_ts):
        if pd.isna(dt):
            out[idx] = np.nan
            continue
        days      = max((dt.normalize() - genesis).days, 0)
        remaining = days * BLOCKS_PER_DAY
        reward, supply = 50.0, 0.0
        for _ in range(40):
            if remaining <= 0 or reward < 1e-12:
                break
            epoch   = min(remaining, BLOCKS_PER_EPOCH)
            supply += epoch * reward
            remaining -= epoch
            reward   *= 0.5
        out[idx] = min(supply, MAX_SUPPLY)
    return pd.Series(out, index=dates.index, dtype=np.float64)


# ─────────────────────────────────────────────────────────────────────────────
# Checkonchain model ingestion (exact series parity)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json_block(text: str, start: int, open_char: str, close_char: str) -> tuple[str, int]:
    """
    Extract a balanced JSON block (array/object) from `text[start:]`.
    Returns (block_text, end_index_exclusive).
    """
    if start >= len(text) or text[start] != open_char:
        raise ValueError("JSON block start is invalid")

    depth = 0
    in_str = False
    escaped = False

    for idx in range(start, len(text)):
        ch = text[idx]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start: idx + 1], idx + 1

    raise ValueError("Unbalanced JSON block")


def _extract_plotly_traces_from_html(html: str) -> list[dict]:
    """
    Parse first Plotly.newPlot(..., data, layout, config) call and return `data`.
    """
    marker = "Plotly.newPlot("
    start = html.find(marker)
    if start < 0:
        raise ValueError("Plotly.newPlot call not found")

    pos = start + len(marker)
    in_str = False
    escaped = False
    depth = 0

    # Skip first argument (div id) until top-level comma.
    while pos < len(html):
        ch = html[pos]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch == "," and depth == 0:
                pos += 1
                break
        pos += 1

    while pos < len(html) and html[pos].isspace():
        pos += 1

    if pos >= len(html) or html[pos] != "[":
        raise ValueError("Plotly data payload not found")

    traces_text, _ = _extract_json_block(html, pos, "[", "]")
    traces = json.loads(traces_text)
    if not isinstance(traces, list):
        raise ValueError("Plotly traces payload is not a list")
    return traces


def _decode_plotly_vector(raw: object) -> np.ndarray:
    """Decode Plotly vectors stored either as plain lists or {dtype,bdata}."""
    if isinstance(raw, list):
        return np.asarray(raw, dtype=np.float64)

    if isinstance(raw, dict) and "bdata" in raw:
        dtype_key = str(raw.get("dtype", "f8")).lower()
        dtype_map = {
            "f8": np.float64,
            "f4": np.float32,
            "i8": np.int64,
            "i4": np.int32,
            "u8": np.uint64,
            "u4": np.uint32,
        }
        dtype = np.dtype(dtype_map.get(dtype_key, np.float64))
        payload = base64.b64decode(raw["bdata"])
        return np.frombuffer(payload, dtype=dtype).astype(np.float64, copy=False)

    return np.array([], dtype=np.float64)


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_checkonchain_onchain_models() -> pd.DataFrame:
    """
    Fetch exact `Price`, `Realised Price`, and `Balanced Price` series from
    Checkonchain's public Onchain Originals chart payload.
    """
    try:
        resp = requests.get(_CHECKONCHAIN_ONCHAIN_ORIGINALS_URL, timeout=_LARGE_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.warning("Checkonchain fetch error: %s", exc)
        return pd.DataFrame(columns=["date", "price_ref", "realized_price", "balanced_price"])

    try:
        traces = _extract_plotly_traces_from_html(html)
    except Exception as exc:
        logger.warning("Checkonchain parse error: %s", exc)
        return pd.DataFrame(columns=["date", "price_ref", "realized_price", "balanced_price"])

    frames: list[pd.DataFrame] = []
    for trace_name, out_col in _CHECKONCHAIN_MODEL_TRACE_MAP.items():
        trace = next((t for t in traces if t.get("name") == trace_name), None)
        if trace is None:
            continue

        x_raw = trace.get("x")
        y_raw = trace.get("y")
        if not isinstance(x_raw, list):
            continue

        y_arr = _decode_plotly_vector(y_raw)
        if y_arr.size == 0:
            continue

        n = min(len(x_raw), int(y_arr.size))
        if n <= 0:
            continue

        tmp = pd.DataFrame({"date": pd.Series(x_raw[:n]), out_col: y_arr[:n]})
        tmp["date"] = _to_utc_naive(tmp["date"]).dt.normalize()
        tmp[out_col] = pd.to_numeric(tmp[out_col], errors="coerce")
        tmp = (tmp
               .dropna(subset=["date", out_col])
               .sort_values("date")
               .drop_duplicates(subset=["date"], keep="last")
               .reset_index(drop=True))
        if not tmp.empty:
            frames.append(tmp[["date", out_col]])

    if not frames:
        return pd.DataFrame(columns=["date", "price_ref", "realized_price", "balanced_price"])

    out = frames[0].copy()
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")

    return (out
            .dropna(subset=["date"])
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True))


# ─────────────────────────────────────────────────────────────────────────────
# Price data fetching — multiple sources
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise any price DataFrame to [date: datetime64[ns] tz-naive, price: float64].
    Deduplicates by date (keep last), sorts ascending, drops non-positive prices.
    Uses _to_utc_naive() to handle mixed tz-aware/naive inputs from any source.
    """
    df = df.copy()
    df["date"]  = _to_utc_naive(df["date"]).dt.normalize()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return (df[["date", "price"]]
            .dropna()
            .query("price > 0")
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True))


def _fetch_prices_yfinance() -> pd.DataFrame:
    """
    yfinance BTC-USD — free, no key. Coverage: ~2014-09-17.
    Returns tz-aware UTC index which _normalise_price_df strips cleanly.
    """
    try:
        import yfinance as yf
        raw = yf.download("BTC-USD", start=_HISTORY_START, progress=False, auto_adjust=True)
        if raw.empty:
            return pd.DataFrame(columns=["date", "price"])
        # yfinance may return MultiIndex columns when auto_adjust=True
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw[["Close"]].copy().reset_index()
        df.columns = ["date", "price"]
        return _normalise_price_df(df)
    except Exception as exc:
        logger.error("yfinance failed: %s", exc)
        return pd.DataFrame(columns=["date", "price"])


def _fetch_coinmetrics_asset_metrics(metrics: Sequence[str]) -> pd.DataFrame:
    """
    Fetch daily BTC metrics from CoinMetrics community API.

    Returns DataFrame with columns: [date] + requested metrics
    (missing metrics are present as NaN).
    """
    metric_list = [m for m in metrics if m]
    if not metric_list:
        return pd.DataFrame(columns=["date"])

    params: dict = {
        "assets": "btc",
        "metrics": ",".join(metric_list),
        "frequency": "1d",
        "start_time": _HISTORY_START,
        "page_size": "10000",
    }
    records: list[dict] = []

    while True:
        try:
            resp = requests.get(_CM_ASSET_METRICS_URL, params=params, timeout=_LARGE_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("CoinMetrics HTTP %s for metrics=%s", resp.status_code, ",".join(metric_list))
                break
            payload = resp.json()
        except Exception as exc:
            logger.warning("CoinMetrics error for metrics=%s: %s", ",".join(metric_list), exc)
            break

        batch = payload.get("data", [])
        if not batch:
            break
        records.extend(batch)

        next_token = payload.get("next_page_token")
        if not next_token:
            break
        params = {"next_page_token": next_token}

    if not records:
        return pd.DataFrame(columns=["date", *metric_list])

    raw = pd.DataFrame(records)
    if "time" in raw.columns:
        raw["date"] = _to_utc_naive(raw["time"].astype(str)).dt.normalize()
    else:
        raw["date"] = pd.NaT

    out = pd.DataFrame({"date": raw["date"]})
    for metric in metric_list:
        if metric in raw.columns:
            out[metric] = pd.to_numeric(raw[metric], errors="coerce")
        else:
            out[metric] = np.nan

    return (out
            .dropna(subset=["date"])
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True))


def _fetch_onchain_coinmetrics() -> pd.DataFrame:
    """
    Fetch on-chain inputs for valuation metrics (non-CryptoQuant):
      - realized_cap (USD): CapRealUSD
      - supply_total (BTC): SplyCur
      - cdd (BTC-days): TxTfrValDayDst (fallback TxTfrValAdjDayDst)
    """
    def _fetch_first_metric(candidates: Sequence[str]) -> tuple[pd.DataFrame, str]:
        for metric in candidates:
            raw = _fetch_coinmetrics_asset_metrics((metric,))
            if raw.empty or metric not in raw.columns:
                continue
            val = pd.to_numeric(raw[metric], errors="coerce")
            tmp = pd.DataFrame({"date": raw["date"], "value": val})
            tmp = (tmp
                   .dropna(subset=["date", "value"])
                   .sort_values("date")
                   .drop_duplicates(subset=["date"], keep="last")
                   .reset_index(drop=True))
            if not tmp.empty:
                return tmp, metric
        return pd.DataFrame(columns=["date", "value"]), ""

    rc_df, rc_metric = _fetch_first_metric(_CM_ONCHAIN_METRIC_CANDIDATES["realized_cap"])
    sp_df, sp_metric = _fetch_first_metric(_CM_ONCHAIN_METRIC_CANDIDATES["supply_total"])
    cdd_df, cdd_metric = _fetch_first_metric(_CM_ONCHAIN_METRIC_CANDIDATES["cdd"])

    logger.info(
        "CoinMetrics metrics selected: realized_cap=%s (%d rows), supply=%s (%d rows), cdd=%s (%d rows)",
        rc_metric or "none", len(rc_df),
        sp_metric or "none", len(sp_df),
        cdd_metric or "none", len(cdd_df),
    )

    frames = []
    if not rc_df.empty:
        frames.append(rc_df.rename(columns={"value": "realized_cap"}))
    if not sp_df.empty:
        frames.append(sp_df.rename(columns={"value": "supply_total"}))
    if not cdd_df.empty:
        frames.append(cdd_df.rename(columns={"value": "cdd"}))

    if not frames:
        return pd.DataFrame(columns=["date", "realized_cap", "supply_total", "cdd"])

    out = frames[0].copy()
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")

    return (out
            .dropna(subset=["date"])
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True))


def _fetch_prices_coinmetrics() -> pd.DataFrame:
    """
    CoinMetrics community API — free, no key. Coverage: 2010-07-18.
    """
    raw = _fetch_coinmetrics_asset_metrics(("PriceUSD",))
    if raw.empty or "PriceUSD" not in raw.columns:
        return pd.DataFrame(columns=["date", "price"])
    out = raw.rename(columns={"PriceUSD": "price"})
    return _normalise_price_df(out[["date", "price"]])


def _fetch_prices_cryptocompare() -> pd.DataFrame:
    """
    CryptoCompare histoday — free, no key. Coverage: 2010-07-17.
    Returns Unix epoch seconds (tz-naive after pd.to_datetime unit='s').
    Paginates backwards via toTs parameter.
    """
    url    = "https://min-api.cryptocompare.com/data/v2/histoday"
    cutoff = pd.Timestamp(_HISTORY_START)
    to_ts: Optional[int] = None
    records: list[dict]  = []

    while True:
        params: dict = {"fsym": "BTC", "tsym": "USD", "limit": 2000}
        if to_ts is not None:
            params["toTs"] = to_ts

        try:
            resp = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(5)
                continue
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.warning("CryptoCompare error: %s", exc)
            break

        batch = payload.get("Data", {}).get("Data", [])
        if not batch:
            break
        batch = [r for r in batch if r.get("close", 0) > 0]
        if not batch:
            break

        records.extend(batch)
        earliest_ts   = min(r["time"] for r in batch)
        earliest_date = pd.Timestamp(earliest_ts, unit="s")

        if earliest_date <= cutoff:
            break

        to_ts = earliest_ts - 1
        time.sleep(0.15)

    if not records:
        return pd.DataFrame(columns=["date", "price"])

    raw = pd.DataFrame(records)
    raw["date"]  = pd.to_datetime(raw["time"], unit="s")  # tz-naive UTC
    raw["price"] = pd.to_numeric(raw["close"], errors="coerce")
    return _normalise_price_df(raw[["date", "price"]])


def _fetch_prices_blockchain_info() -> pd.DataFrame:
    """
    Blockchain.info market-price chart — free, no key. Coverage: ~2009-01-03.
    Returns Unix epoch seconds (tz-naive after pd.to_datetime unit='s').
    Single bulk request with sampled=false for full daily resolution.
    """
    url    = "https://api.blockchain.info/charts/market-price"
    params = {"timespan": "all", "format": "json", "sampled": "false"}
    try:
        resp = requests.get(url, params=params, timeout=_LARGE_TIMEOUT)
        resp.raise_for_status()
        values = resp.json().get("values", [])
    except Exception as exc:
        logger.warning("Blockchain.info error: %s", exc)
        return pd.DataFrame(columns=["date", "price"])

    if not values:
        return pd.DataFrame(columns=["date", "price"])

    raw = pd.DataFrame(values)
    raw["date"]  = pd.to_datetime(raw["x"], unit="s")  # tz-naive UTC
    raw["price"] = pd.to_numeric(raw["y"], errors="coerce")
    return _normalise_price_df(raw[["date", "price"]])


def _fetch_prices_coingecko() -> pd.DataFrame:
    """
    CoinGecko market_chart — free tier, no key. Coverage: ~2013-04-28.
    Returns Unix epoch milliseconds (tz-naive after pd.to_datetime unit='ms').
    Rate-limited on free tier (~30 req/min).
    """
    url     = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params  = {"vs_currency": "usd", "days": "max", "interval": "daily"}
    headers = {"accept": "application/json"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=_REQUEST_TIMEOUT)
        if resp.status_code == 429:
            logger.warning("CoinGecko rate-limited")
            return pd.DataFrame(columns=["date", "price"])
        resp.raise_for_status()
        prices = resp.json().get("prices", [])
    except Exception as exc:
        logger.warning("CoinGecko error: %s", exc)
        return pd.DataFrame(columns=["date", "price"])

    if not prices:
        return pd.DataFrame(columns=["date", "price"])

    raw = pd.DataFrame(prices, columns=["ts", "price"])
    raw["date"] = pd.to_datetime(raw["ts"], unit="ms")  # tz-naive UTC
    return _normalise_price_df(raw[["date", "price"]])


# Source registry: (name, fetcher_fn, approx_coverage_start)
# Priority order for overlapping dates: lower index = higher priority.
# yfinance is listed first because it is the most reliable and consistently
# available; it fills recent history. Earlier-start sources fill the 2010-2014
# gap that yfinance cannot reach.
_PRICE_SOURCES: list[tuple[str, object, str]] = [
    ("yfinance",        _fetch_prices_yfinance,        "2014-09-17"),
    ("coinmetrics",     _fetch_prices_coinmetrics,     "2010-07-18"),
    ("cryptocompare",   _fetch_prices_cryptocompare,   "2010-07-17"),
    ("blockchain_info", _fetch_prices_blockchain_info, "2009-01-03"),
    ("coingecko",       _fetch_prices_coingecko,       "2013-04-28"),
]

_SOURCE_PRIORITY = {name: i for i, (name, _, _) in enumerate(_PRICE_SOURCES)}


def _fetch_btc_price_full_history() -> tuple[pd.DataFrame, str]:
    """
    Build maximum-coverage BTC price history by attempting all registered
    sources. For any given date the highest-priority source wins.

    Returns (price_df[date, price], source_summary_string).
    """
    frames: list[tuple[str, pd.DataFrame]] = []

    for name, fetcher, _ in _PRICE_SOURCES:
        try:
            df = fetcher()  # type: ignore[operator]
            if not df.empty:
                frames.append((name, df))
                logger.info("Price '%s': %d rows, earliest %s",
                            name, len(df), df["date"].min().date())
        except Exception as exc:
            logger.warning("Price source '%s' failed: %s", name, exc)

    if not frames:
        return pd.DataFrame(columns=["date", "price"]), "none"

    tagged: list[pd.DataFrame] = []
    for name, df in frames:
        pri = _SOURCE_PRIORITY.get(name, 99)
        tmp = df.copy()
        tmp["_pri"] = pri
        tagged.append(tmp)

    # All date columns are guaranteed tz-naive by _normalise_price_df,
    # so pd.concat will not raise "Cannot mix tz-aware with tz-naive".
    merged = pd.concat(tagged, ignore_index=True)

    # Belt-and-suspenders: re-apply _to_utc_naive in case any frame slipped through
    merged["date"]  = _to_utc_naive(merged["date"]).dt.normalize()
    merged["price"] = pd.to_numeric(merged["price"], errors="coerce")
    merged = (merged
              .dropna(subset=["date", "price"])
              .query("price > 0")
              .sort_values(["date", "_pri"])
              .drop_duplicates(subset=["date"], keep="first")
              .sort_values("date")
              .reset_index(drop=True))

    source_names = [name for name, _ in frames]
    summary      = " + ".join(source_names)
    earliest     = merged["date"].min().strftime("%Y-%m-%d") if not merged.empty else "?"
    logger.info("Merged price: %d rows, earliest %s, sources: %s",
                len(merged), earliest, summary)

    return merged[["date", "price"]], summary


# ─────────────────────────────────────────────────────────────────────────────
# On-chain series helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_value_df(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Convert [date, col] → [date, value] for _left_join compatibility."""
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=["date", "value"])
    out = df[["date", col]].copy()
    out.columns = ["date", "value"]
    out["date"] = _to_utc_naive(out["date"]).dt.normalize()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return (out
            .dropna(subset=["date", "value"])
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
            .reset_index(drop=True))


# ─────────────────────────────────────────────────────────────────────────────
# Dataset builder (cached)
# ─────────────────────────────────────────────────────────────────────────────

def _left_join(base: pd.DataFrame, extra: pd.DataFrame, col: str) -> pd.DataFrame:
    """Left-join a [date, value] DataFrame onto base by date (tz-safe)."""
    if extra.empty:
        base[col] = np.nan
        return base
    tmp = extra.rename(columns={"value": col}).copy()
    tmp["date"] = _to_utc_naive(tmp["date"]).dt.normalize()
    tmp = tmp.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
    return base.merge(tmp[["date", col]], on="date", how="left")


@st.cache_data(show_spinner=False, ttl=3600)
def _build_dataset() -> tuple[pd.DataFrame, MetricResult, str]:
    """
    Full pipeline: fetch → merge → compute → assemble chart DataFrame.

    Returns (chart_df, MetricResult, price_source_summary).
    """
    # ── Base price source ─────────────────────────────────────────────────────
    price_df = _fetch_prices_yfinance()
    price_src = "yfinance"

    # ── Primary model feed: exact Checkonchain Onchain Originals lines ───────
    models = _fetch_checkonchain_onchain_models()
    if price_df.empty:
        if not models.empty and "price_ref" in models.columns:
            fallback_price = models[["date", "price_ref"]].rename(columns={"price_ref": "price"})
            price_df = _normalise_price_df(fallback_price)
            price_src = "checkonchain"
        else:
            empty = MetricResult(df=pd.DataFrame(), has_onchain=False,
                                 warnings=["BTC price unavailable from yfinance and checkonchain."])
            return pd.DataFrame(), empty, "none"

    # Final tz-safe normalisation on the merged price spine
    price_df["date"] = _to_utc_naive(price_df["date"]).dt.normalize()
    price_df = (price_df
                .query("price > 0")
                .sort_values("date")
                .drop_duplicates(subset=["date"], keep="last")
                .reset_index(drop=True))

    have_exact_models = (
        not models.empty and
        {"realized_price", "balanced_price"}.issubset(models.columns)
    )

    if have_exact_models:
        if "price_ref" in models.columns and pd.to_numeric(models["price_ref"], errors="coerce").notna().any():
            price_src = "checkonchain + yfinance fallback"
        ref_cols = [c for c in ("date", "price_ref", "realized_price", "balanced_price") if c in models.columns]
        ref = (models[ref_cols]
               .copy()
               .sort_values("date")
               .drop_duplicates(subset=["date"], keep="last")
               .reset_index(drop=True))

        last_ref_date = pd.to_datetime(ref["date"], errors="coerce").max()
        df = price_df.copy()
        if pd.notna(last_ref_date):
            df = df[df["date"] <= last_ref_date].copy()
        df = df.merge(ref, on="date", how="left")
        if "price_ref" in df.columns:
            df["price"] = pd.to_numeric(df["price_ref"], errors="coerce").combine_first(df["price"])
        df["realized_price"] = pd.to_numeric(df["realized_price"], errors="coerce").ffill()
        df["balanced_price"] = pd.to_numeric(df["balanced_price"], errors="coerce").ffill()

        transferred = (df["realized_price"] - df["balanced_price"]).astype("float64")
        terminal = (TERMINAL_MULTIPLIER * transferred).astype("float64")

        reliable_mask = df["date"] >= pd.Timestamp(MetricConfig().reliable_start_date)
        df.loc[~reliable_mask, ["realized_price", "balanced_price"]] = np.nan
        transferred = transferred.where(reliable_mask, np.nan)
        terminal = terminal.where(reliable_mask, np.nan)

        # Keep strict log-scale-safe values only.
        for col in ("realized_price", "balanced_price"):
            df[col] = df[col].where(np.isfinite(df[col]) & (df[col] > 0), np.nan)
        transferred = transferred.where(np.isfinite(transferred) & (transferred > 0), np.nan)
        terminal = terminal.where(np.isfinite(terminal) & (terminal > 0), np.nan)

        metric_df = pd.DataFrame({
            "price": df["price"].astype("float64").to_numpy(),
            "realized_price": df["realized_price"].astype("float64").to_numpy(),
            "transferred_price": transferred.astype("float64").to_numpy(),
            "balanced_price": df["balanced_price"].astype("float64").to_numpy(),
            "terminal_price": terminal.astype("float64").to_numpy(),
        }, dtype=np.float64)
        result = MetricResult(df=metric_df, has_onchain=True, warnings=[])
        chart_df = df[["date"]].copy()
        for col in ("price", "realized_price", "transferred_price", "balanced_price", "terminal_price"):
            chart_df[col] = result.df[col].to_numpy(dtype="float64")
    else:
        # Fallback path (offline/unavailable): local approximation without
        # external on-chain inputs.
        df = price_df.copy()
        df["supply_total"] = estimate_supply_from_schedule(df["date"]).astype("float64")
        result = compute_metrics(
            price=df["price"].astype("float64"),
            supply=df["supply_total"].astype("float64"),
            realized_cap=None,
            cdd=None,
            dates=df["date"],
        )
        result.warnings = ["Exact Checkonchain model feed unavailable; using local approximation."]

        chart_df = df[["date"]].copy()
        for col in ("price", "realized_price", "transferred_price", "balanced_price", "terminal_price"):
            chart_df[col] = result.df[col].to_numpy(dtype="float64")

    # Display consistency: derive terminal directly from realized-balanced
    # when available (same source family), with transferred fallback.
    transferred_disp = pd.to_numeric(chart_df.get("transferred_price"), errors="coerce")
    realized_disp = pd.to_numeric(chart_df.get("realized_price"), errors="coerce")
    balanced_disp = pd.to_numeric(chart_df.get("balanced_price"), errors="coerce")

    terminal_from_rb = (realized_disp - balanced_disp) * TERMINAL_MULTIPLIER
    terminal_from_tr = transferred_disp * TERMINAL_MULTIPLIER
    terminal_disp = terminal_from_rb.combine_first(terminal_from_tr)
    terminal_disp = terminal_disp.where(np.isfinite(terminal_disp) & (terminal_disp > 0), np.nan)
    chart_df["terminal_price"] = terminal_disp.astype("float64")

    # Ratios are always derived from final metric columns (post-override).
    result.df = chart_df[["price", "realized_price", "transferred_price", "balanced_price", "terminal_price"]].copy()
    result.add_ratio_columns()
    for col in ("ratio_price_terminal", "ratio_price_realized", "ratio_price_balanced"):
        chart_df[col] = result.df[col].to_numpy(dtype="float64")

    chart_df["price"] = chart_df["price"].clip(lower=1e-6)
    return chart_df, result, price_src


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _base_layout(fig: go.Figure) -> None:
    fig.update_layout(
        height=_CHART_HEIGHT,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=30, r=20, t=10, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6e9ef", size=13),
        dragmode="zoom",
        legend=dict(orientation="h", yanchor="top", y=-0.18,
                    xanchor="left", x=0.0, font=dict(color="#e6e9ef")),
        hoverlabel=dict(bgcolor="#0b0f14",
                        bordercolor="rgba(96,165,250,0.4)",
                        font=dict(color="#e6e9ef")),
        uirevision="btc-terminal-price-chart",
    )
    fig.update_xaxes(
        title_text="Date", showgrid=False, zeroline=False, tickformat="%Y",
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikedash="dot", spikecolor="rgba(255,255,255,0.5)", spikethickness=0.4,
    )


def _log_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for col, name, width in [
        ("price",          "Bitcoin Price",  1.8),
        ("terminal_price", "Terminal Price", 1.8),
        ("realized_price", "Realized Price", 1.7),
        ("balanced_price", "Balanced Price", 1.7),
    ]:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col], mode="lines", name=name,
            line=dict(color=_CHART_COLORS[col], width=width),
            hovertemplate=f"{name}: $%{{y:,.2f}}<extra></extra>",
        ))
    _base_layout(fig)
    fig.update_yaxes(title_text="Price (USD)", type="log",
                     showgrid=True, gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig


def _ratio_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for col, name, color_key in [
        ("ratio_price_terminal", "Price / Terminal", "terminal_price"),
        ("ratio_price_realized", "Price / Realized", "realized_price"),
        ("ratio_price_balanced", "Price / Balanced", "balanced_price"),
    ]:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col], mode="lines", name=name,
            line=dict(color=_CHART_COLORS[color_key], width=1.6),
            hovertemplate=f"{name}: %{{y:.3f}}<extra></extra>",
        ))
    fig.add_hline(
        y=1.0,
        line=dict(color=_CHART_COLORS["ratio_ref"], width=1.2, dash="dot"),
        annotation_text="Fair Value (ratio = 1)",
        annotation_font_color=_CHART_COLORS["ratio_ref"],
    )
    _base_layout(fig)
    fig.update_yaxes(title_text="Ratio (Price / Metric)", type="linear",
                     showgrid=True, gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit render
# ─────────────────────────────────────────────────────────────────────────────

def render(context: dict) -> None:
    favourites       = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    with st.spinner("Fetching yfinance price + Checkonchain model lines…"):
        chart_df, result, price_src = _build_dataset()

    if chart_df.empty:
        st.error("BTC price data is unavailable from yfinance/checkonchain.")
        return

    TITLE      = "Bitcoin Terminal, Realized & Balanced Price"
    last_date  = pd.to_datetime(chart_df["date"]).max()
    first_date = pd.to_datetime(chart_df["date"]).min()
    last_text  = last_date.strftime("%Y-%m-%d")  if pd.notna(last_date)  else "—"
    first_text = first_date.strftime("%Y-%m-%d") if pd.notna(first_date) else "—"
    onchain_label = (
        "YFinance price + Checkonchain Onchain Originals (model lines from 2016)"
        if result.has_onchain
        else "Fallback model in use (Checkonchain feed unavailable; lines from 2016)"
    )

    # ── Header ────────────────────────────────────────────────────────────────
    header_cols = st.columns([6, 1], gap="small")
    with header_cols[0]:
        st.markdown(
            f'<div class="charts-header">'
            f'<h3>{TITLE}</h3>'
            f'<div class="charts-meta">'
            f'History: {first_text} – {last_text} &nbsp;·&nbsp; '
            f'Price: {price_src} &nbsp;·&nbsp; {onchain_label}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        is_fav = TITLE in favourites
        st.markdown(
            f'<div class="charts-filter-label">{"★ Saved" if is_fav else "☆ Save"}</div>',
            unsafe_allow_html=True,
        )
        if toggle_favourite:
            toggle_favourite(TITLE, "btc_terminal_price")

    # ── Warnings ──────────────────────────────────────────────────────────────
    for w in result.warnings:
        st.warning(w, icon="⚠️")
    if not result.has_onchain:
        st.info(
            "Checkonchain model feed is unavailable, so local approximation "
            "is used for valuation lines.",
            icon="ℹ️",
        )

    # ── View toggle ───────────────────────────────────────────────────────────
    view_mode = st.radio(
        "View", ["Log Price", "Ratio (Price / Metric)"],
        horizontal=True, label_visibility="collapsed",
    )

    with st.container(border=True):
        fig = _log_chart(chart_df) if view_mode == "Log Price" else _ratio_chart(chart_df)
        st.plotly_chart(fig, use_container_width=True, key="btc_terminal_price_plot",
                        config={"displayModeBar": False, "scrollZoom": False,
                                "doubleClick": "reset", "showTips": False, "responsive": True})

    # ── Current values snapshot ───────────────────────────────────────────────
    latest = chart_df.iloc[-1]
    for widget, (label, field) in zip(
        st.columns(4),
        [("BTC Price", "price"), ("Terminal", "terminal_price"),
         ("Realized",  "realized_price"), ("Balanced", "balanced_price")],
    ):
        v = latest.get(field, np.nan)
        widget.metric(label, f"${v:,.0f}" if pd.notna(v) and v > 0 else "—")

    # ── Description ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="charts-description">
          <h4>Formula Reference</h4>
          <p><strong>Realized Price</strong> and <strong>Balanced Price</strong>
             follow the Checkonchain Onchain Originals published series.</p>
          <p><strong>Transferred Price (implied)</strong> =
             Realized Price − Balanced Price.</p>
          <p><strong>Balanced Price</strong> = Realized Price − Transferred Price.</p>
          <p><strong>Terminal Price</strong> = 21 × Transferred Price.
             Historically aligns with major cycle tops.</p>
          <h4>Ratio View</h4>
          <p>Price ÷ each valuation metric, normalised to 1.0. Above 1 = price
             exceeds that cost basis; below 1 = price at a discount to it.</p>
          <h4>Price Data Sources</h4>
          <p>Price and model lines are sourced from the public Checkonchain
             Onchain Originals chart payload (with yfinance price fallback).
             If unavailable, local fallback estimation is used. Model lines are
             masked before 2016-01-01. All computation is in float64.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
