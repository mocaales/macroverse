import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import (
    fetch_btc_prices,
    fetch_eth_prices,
    fetch_gold_prices,
    fetch_silver_prices,
    fetch_spx500_prices,
    fetch_qqq_prices,
    fetch_yfinance_symbol_prices,
)


AVG_OPTIONS = [
    ("all_years", "All Years"),
    ("election_years", "Election Years"),
    ("post_election_years", "Post-Election Years"),
    ("midterm_years", "Midterm Years"),
    ("pre_election_years", "Pre-Election Years"),
]

_AVG_LINE_COLORS = {
    "all_years": "#f8fafc",
    "election_years": "#f59e0b",
    "post_election_years": "#22d3ee",
    "midterm_years": "#a78bfa",
    "pre_election_years": "#34d399",
}

_METRIC_CONFIG = {
    "BTC (Bitcoin)": {
        "key": "btc",
        "name": "Bitcoin",
        "min_year": 2011,
        "category": "Crypto",
    },
    "ETH (Ethereum)": {
        "key": "eth",
        "name": "Ethereum",
        "min_year": 2015,
        "category": "Crypto",
    },
    "GOLD (Gold)": {
        "key": "gold",
        "name": "Gold",
        "min_year": 1970,
        "category": "Commodities",
    },
    "SILVER (Silver)": {
        "key": "silver",
        "name": "Silver",
        "min_year": 1970,
        "category": "Commodities",
    },
    "SPX500 (S&P 500)": {
        "key": "spx500",
        "name": "S&P 500",
        "min_year": 1950,
        "category": "IDXs",
    },
    "QQQ (Nasdaq-100 ETF)": {
        "key": "qqq",
        "name": "QQQ",
        "min_year": 1999,
        "category": "IDXs",
    },
    "AAPL (Apple)": {
        "key": "aapl",
        "name": "Apple",
        "min_year": 1980,
        "category": "Stocks",
    },
    "AMZN (Amazon)": {
        "key": "amzn",
        "name": "Amazon",
        "min_year": 1997,
        "category": "Stocks",
    },
    "GOOGL (Alphabet)": {
        "key": "googl",
        "name": "Alphabet",
        "min_year": 2004,
        "category": "Stocks",
    },
    "META (Meta)": {
        "key": "meta",
        "name": "Meta",
        "min_year": 2012,
        "category": "Stocks",
    },
    "MSFT (Microsoft)": {
        "key": "msft",
        "name": "Microsoft",
        "min_year": 1986,
        "category": "Stocks",
    },
    "NVDA (NVIDIA)": {
        "key": "nvda",
        "name": "NVIDIA",
        "min_year": 1999,
        "category": "Stocks",
    },
    "TSLA (Tesla)": {
        "key": "tsla",
        "name": "Tesla",
        "min_year": 2010,
        "category": "Stocks",
    },
}

_CATEGORY_ORDER = ["Crypto", "Stocks", "Commodities", "IDXs"]


def _series_color(year: int) -> str:
    hue = (year * 41) % 360
    return f"hsl({hue}, 72%, 56%)"


def _year_bucket(year: int) -> str:
    mod = year % 4
    if mod == 0:
        return "election_years"
    if mod == 1:
        return "post_election_years"
    if mod == 2:
        return "midterm_years"
    return "pre_election_years"


def _build_ytd_dataframe(df: pd.DataFrame, min_year: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    frame = df.sort_values("date").dropna(subset=["price"]).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["price"])
    frame = frame[frame["price"] > 0]
    if frame.empty:
        return pd.DataFrame()

    frame["year"] = frame["date"].dt.year
    frame = frame[frame["year"] >= min_year]
    if frame.empty:
        return pd.DataFrame()

    items = []
    for year, year_df in frame.groupby("year"):
        year_df = year_df.sort_values("date").copy()
        jan_start = pd.Timestamp(year=year, month=1, day=1)
        first_row = year_df[year_df["date"] >= jan_start].head(1)
        if first_row.empty:
            continue
        base = float(first_row["price"].iloc[0])
        if not np.isfinite(base) or base <= 0:
            continue

        year_df["day"] = (year_df["date"] - jan_start).dt.days
        year_df["roi"] = year_df["price"] / base
        year_df["roi"] = year_df["roi"].replace([np.inf, -np.inf], np.nan)
        year_df = year_df.dropna(subset=["roi"])
        if year_df.empty:
            continue

        # ── Deduplicate to one row per calendar day (keep last = closing price).
        # Multiple intraday rows with the same integer `day` would otherwise cause
        # oscillating lines in both individual year traces and cross-year averages.
        year_df = (
            year_df.sort_values("date")
            .drop_duplicates(subset=["day"], keep="last")
        )

        # Align all years to a non-leap calendar-day index to avoid leap-year
        # discontinuities in cross-year averages.
        year_df["month_day"] = year_df["date"].dt.strftime("%m-%d")
        year_df = year_df[year_df["month_day"] != "02-29"]
        if year_df.empty:
            continue
        ref_days = pd.to_datetime(
            "2001-" + year_df["month_day"],
            format="%Y-%m-%d",
            errors="coerce",
        )
        year_df["day"] = ref_days.dt.dayofyear - 1
        year_df = year_df.dropna(subset=["day"]).copy()
        year_df["day"] = year_df["day"].astype(int)

        year_df["label"] = str(year)
        items.append(year_df[["day", "roi", "year", "label", "date"]])

    if not items:
        return pd.DataFrame()
    return pd.concat(items, ignore_index=True)


def _compute_average_series(
    ytd_df: pd.DataFrame,
    series_name: str,
    current_year: int,
) -> pd.DataFrame:
    """
    Mean ROI curve across all historical years in the given bucket.
    current_year excluded so a partial year does not bias the average.
    Data is already deduplicated to one row per (year, day) at this point.
    """
    if ytd_df.empty:
        return pd.DataFrame()
    base = ytd_df[ytd_df["year"] != current_year].copy()
    if base.empty:
        return pd.DataFrame()

    if series_name != "all_years":
        # Election-cycle buckets are more stable from 2012 onward.
        # 2011 is a partial early-market year and can distort grouped averages.
        base = base[base["year"] >= 2012]
        base = base[base["year"].apply(lambda y: _year_bucket(int(y)) == series_name)]
    if base.empty:
        return pd.DataFrame()

    return _compute_average_from_base(base)


def _compute_average_from_base(base: pd.DataFrame) -> pd.DataFrame:
    base = base[base["roi"] > 0].copy()
    if base.empty:
        return pd.DataFrame()

    # Use geometric mean in log space to reduce outlier distortion between years.
    log_df = base.copy()
    log_df["log_roi"] = np.log(log_df["roi"])
    # First smooth each year individually with a 5-day moving average.
    log_df = log_df.sort_values(["year", "day"])
    log_df["log_roi"] = log_df.groupby("year")["log_roi"].transform(
        lambda s: s.rolling(window=5, min_periods=2, center=True).mean()
    )
    log_df = log_df.dropna(subset=["log_roi"])

    avg_df = log_df.groupby("day", as_index=False)["log_roi"].mean()
    avg_df = avg_df.sort_values("day")

    # Smooth the average curve with a 5-day moving average.
    avg_df["log_roi"] = avg_df["log_roi"].rolling(
        window=5,
        min_periods=2,
        center=True,
    ).mean()

    avg_df["roi"] = np.exp(avg_df["log_roi"])
    avg_df["roi"] = avg_df["roi"].replace([np.inf, -np.inf], np.nan)
    return avg_df.dropna(subset=["roi"])[["day", "roi"]]


def _compute_custom_average_series(ytd_df: pd.DataFrame, selected_years: tuple[int, ...]) -> pd.DataFrame:
    if ytd_df.empty or not selected_years:
        return pd.DataFrame()
    base = ytd_df[ytd_df["year"].isin(selected_years)].copy()
    if base.empty:
        return pd.DataFrame()
    return _compute_average_from_base(base)


def _compute_std_band_from_base(base: pd.DataFrame) -> pd.DataFrame:
    base = base[base["roi"] > 0].copy()
    if base.empty:
        return pd.DataFrame()

    # Smooth each year first, then compute cross-year mean and standard deviation.
    smooth = base.sort_values(["year", "day"]).copy()
    smooth["roi"] = smooth.groupby("year")["roi"].transform(
        lambda s: s.rolling(window=5, min_periods=2, center=True).mean()
    )
    smooth = smooth.dropna(subset=["roi"])
    if smooth.empty:
        return pd.DataFrame()

    stats = smooth.groupby("day")["roi"].agg(mean="mean", std="std").reset_index()
    stats["std"] = stats["std"].fillna(0.0)
    stats = stats.sort_values("day")
    stats["mean"] = stats["mean"].rolling(window=5, min_periods=2, center=True).mean()
    stats["std"] = stats["std"].rolling(window=5, min_periods=2, center=True).mean()
    stats = stats.dropna(subset=["mean", "std"]).copy()
    if stats.empty:
        return pd.DataFrame()

    stats["lower"] = (stats["mean"] - stats["std"]).clip(lower=1e-4)
    stats["upper"] = (stats["mean"] + stats["std"]).clip(lower=1e-4)
    stats["upper"] = np.maximum(stats["upper"], stats["lower"] * 1.0001)
    return stats[["day", "mean", "std", "lower", "upper"]]


def _compute_custom_std_band(ytd_df: pd.DataFrame, selected_years: tuple[int, ...]) -> pd.DataFrame:
    if ytd_df.empty or not selected_years:
        return pd.DataFrame()
    base = ytd_df[ytd_df["year"].isin(selected_years)].copy()
    if base.empty:
        return pd.DataFrame()
    return _compute_std_band_from_base(base)


def _custom_series_label(selected_years: tuple[int, ...]) -> str:
    years = sorted(int(y) for y in selected_years)
    if len(years) == 1:
        return f"avg({years[0]})"
    if len(years) == 2:
        return f"avg({years[0]}, {years[1]})"
    return f"avg(..., {years[-2]}, {years[-1]}, ...)"


def _std_series_label(selected_years: tuple[int, ...]) -> str:
    years = sorted(int(y) for y in selected_years)
    if len(years) == 1:
        return f"sd({years[0]})"
    if len(years) == 2:
        return f"sd({years[0]}, {years[1]})"
    return f"sd(..., {years[-2]}, {years[-1]}, ...)"


def _selected_years_short_label(selected_years: tuple[int, ...], fallback: str) -> str:
    years = sorted(int(y) for y in selected_years)
    if not years:
        return fallback
    if len(years) <= 3:
        return ", ".join(str(y) for y in years)
    return f"{years[0]}, {years[1]}, ... {years[-1]}"


def _avg_option_label(avg_key: str, ytd_df: pd.DataFrame, current_year: int) -> str:
    source = ytd_df[ytd_df["year"] != current_year]
    if source.empty:
        base_label = next((label for key, label in AVG_OPTIONS if key == avg_key), avg_key)
        return base_label

    years = sorted(source["year"].unique().tolist())
    if avg_key != "all_years":
        years = [y for y in years if y >= 2012]
        years = [y for y in years if _year_bucket(int(y)) == avg_key]

    base_label = next((label for key, label in AVG_OPTIONS if key == avg_key), avg_key)
    if len(years) < 2:
        return base_label
    return f"{base_label} (..., {years[-2]}, {years[-1]}, ...)"


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_ytd_roi(metric_key: str) -> pd.DataFrame:
    if metric_key == "eth":
        prices_df = fetch_eth_prices()
        min_year = _METRIC_CONFIG["ETH (Ethereum)"]["min_year"]
    elif metric_key == "gold":
        prices_df = fetch_gold_prices()
        min_year = _METRIC_CONFIG["GOLD (Gold)"]["min_year"]
    elif metric_key == "silver":
        prices_df = fetch_silver_prices()
        min_year = _METRIC_CONFIG["SILVER (Silver)"]["min_year"]
    elif metric_key == "spx500":
        prices_df = fetch_spx500_prices()
        min_year = _METRIC_CONFIG["SPX500 (S&P 500)"]["min_year"]
    elif metric_key == "qqq":
        prices_df = fetch_qqq_prices()
        min_year = _METRIC_CONFIG["QQQ (Nasdaq-100 ETF)"]["min_year"]
    elif metric_key in {"aapl", "amzn", "googl", "meta", "msft", "nvda", "tsla"}:
        prices_df = fetch_yfinance_symbol_prices(metric_key.upper())
        selected_cfg = next((cfg for cfg in _METRIC_CONFIG.values() if cfg["key"] == metric_key), None)
        min_year = int(selected_cfg["min_year"]) if selected_cfg else 1990
    else:
        prices_df = fetch_btc_prices()
        min_year = _METRIC_CONFIG["BTC (Bitcoin)"]["min_year"]
    if prices_df.empty:
        return pd.DataFrame()
    return _build_ytd_dataframe(prices_df, min_year=min_year)


def render(context: dict) -> None:
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    metric_options = list(_METRIC_CONFIG.keys())
    metric_choice = st.session_state.get("ytd_metric", metric_options[0])
    if metric_choice not in _METRIC_CONFIG:
        metric_choice = metric_options[0]
    metric_info = _METRIC_CONFIG[metric_choice]
    metric_key = metric_info["key"]
    asset_name = metric_info["name"]
    state_prefix = f"ytd_{metric_key}"
    category_options = [c for c in _CATEGORY_ORDER if any(v["category"] == c for v in _METRIC_CONFIG.values())]
    assets_by_category = {
        cat: [label for label, cfg in _METRIC_CONFIG.items() if cfg["category"] == cat]
        for cat in category_options
    }

    custom_series_key = f"{state_prefix}_custom_series_years"
    custom_pick_key = f"{state_prefix}_custom_years_pick"
    custom_add_btn_key = f"{state_prefix}_add_custom_series_btn"
    std_series_key = f"{state_prefix}_std_series_years"
    std_pick_key = f"{state_prefix}_std_years_pick"
    std_add_btn_key = f"{state_prefix}_add_std_btn"
    scale_key = f"{state_prefix}_scale"
    sd_multiplier_key = f"{state_prefix}_sd_multiplier"
    asset_category_key = "ytd_asset_category"
    asset_pick_key = "ytd_asset_pick"
    asset_apply_key = "ytd_asset_apply"
    asset_cancel_key = "ytd_asset_cancel"

    ytd_df = _cached_ytd_roi(metric_key)
    if ytd_df.empty:
        st.error(f"{asset_name} price data is unavailable. Check your connection or data providers.")
        return

    latest_date = pd.to_datetime(ytd_df["date"]).max()
    current_year = int(latest_date.year)
    years = sorted(ytd_df["year"].unique().tolist())

    if custom_series_key not in st.session_state:
        st.session_state[custom_series_key] = tuple()
    if custom_pick_key not in st.session_state:
        st.session_state[custom_pick_key] = []
    if std_series_key not in st.session_state:
        st.session_state[std_series_key] = tuple()
    if std_pick_key not in st.session_state:
        st.session_state[std_pick_key] = []
    if scale_key not in st.session_state:
        st.session_state[scale_key] = "Logarithmic"
    if sd_multiplier_key not in st.session_state:
        st.session_state[sd_multiplier_key] = 1
    if asset_category_key not in st.session_state:
        st.session_state[asset_category_key] = metric_info["category"]

    st.markdown(
        """
        <style>
        /* Streamlit multiselect chips (selected years) */
        div[data-baseweb="tag"] {
          background-color: rgba(148, 163, 184, 0.22) !important;
          border: 1px solid rgba(148, 163, 184, 0.52) !important;
          border-radius: 9999px !important;
          box-shadow: none !important;
        }
        div[data-baseweb="tag"] > span,
        div[data-baseweb="tag"] span {
          background: transparent !important;
          color: rgba(230, 233, 239, 0.92) !important;
          font-weight: 600 !important;
        }
        div[data-baseweb="tag"] button,
        div[data-baseweb="tag"] [role="button"] {
          background: transparent !important;
          color: rgba(230, 233, 239, 0.75) !important;
          border-radius: 9999px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(#charts-filters) .stPopover > button {
          background: rgba(11, 15, 20, 0.8) !important;
          border: 1px solid rgba(255, 255, 255, 0.12) !important;
          border-radius: 12px !important;
          min-height: 2.6rem !important;
          color: #e6e9ef !important;
          font-weight: 600 !important;
          width: 100% !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(#charts-filters) .stPopover > button:hover {
          border-color: rgba(56, 189, 248, 0.45) !important;
        }
        .stPopover div[data-baseweb="radio"] [role="radiogroup"] {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
          padding: 0.3rem;
          border-radius: 10px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(11, 15, 20, 0.85);
        }
        .stPopover div[data-baseweb="radio"] label > div {
          border-radius: 8px;
          padding: 0.35rem 0.55rem;
          border: 1px solid transparent;
        }
        .stPopover div[data-baseweb="radio"] input:checked + div {
          border: 1px solid rgba(59, 130, 246, 0.6);
          background: rgba(59, 130, 246, 0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Header ──────────────────────────────────────────────────────────────────
    header_cols = st.columns([6, 1], gap="small")
    with header_cols[0]:
        st.markdown(
            """
            <div class="charts-header">
              <h3>Year-To-Date ROI</h3>
              <div class="charts-meta">%s annual ROI from Jan 1 through year-end (or current date)</div>
            </div>
            """ % asset_name,
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        is_fav = "Year-To-Date ROI" in favourites
        fav_label = "Favourites" if is_fav else "Favourite"
        st.markdown(
            f'<div class="charts-filter-label">{fav_label}</div>',
            unsafe_allow_html=True,
        )
        if toggle_favourite:
            toggle_favourite("Year-To-Date ROI", "btc_ytd_roi")

    # ── Filters ─────────────────────────────────────────────────────────────────
    year_options = [str(y) for y in years]
    popover_fn = getattr(st, "popover", None)
    selected_avg_keys: list[str] = []
    current_custom = tuple(y for y in st.session_state.get(custom_series_key, tuple()) if y in years)
    st.session_state[custom_series_key] = current_custom
    st.session_state[custom_pick_key] = [
        y for y in st.session_state.get(custom_pick_key, []) if y in year_options
    ]
    if not st.session_state[custom_pick_key] and current_custom:
        st.session_state[custom_pick_key] = [str(y) for y in current_custom]

    current_std = tuple(y for y in st.session_state.get(std_series_key, tuple()) if y in years)
    st.session_state[std_series_key] = current_std
    st.session_state[std_pick_key] = [
        y for y in st.session_state.get(std_pick_key, []) if y in year_options
    ]
    if not st.session_state[std_pick_key] and current_std:
        st.session_state[std_pick_key] = [str(y) for y in current_std]

    if st.session_state.get(asset_category_key) not in category_options:
        st.session_state[asset_category_key] = metric_info["category"]

    filter_wrap = st.columns([0.25, 3.9, 0.25], gap="small")
    with filter_wrap[1]:
        st.markdown('<div id="charts-filters"></div>', unsafe_allow_html=True)
        filter_cols = st.columns([1.5, 1.0, 1.25, 0.8, 1.35], gap="small")

        with filter_cols[0]:
            st.markdown('<div class="charts-filter-label">Price Or Metric</div>', unsafe_allow_html=True)
            if popover_fn:
                with popover_fn(metric_choice):
                    st.markdown('<div class="charts-filter-label">Category</div>', unsafe_allow_html=True)
                    st.radio(
                        "Category",
                        options=category_options,
                        horizontal=True,
                        key=asset_category_key,
                        label_visibility="collapsed",
                    )
                    asset_options = assets_by_category.get(st.session_state[asset_category_key], [])
                    st.markdown('<div class="charts-filter-label">Assets</div>', unsafe_allow_html=True)
                    if asset_options:
                        if st.session_state.get(asset_pick_key) not in asset_options:
                            st.session_state[asset_pick_key] = (
                                metric_choice if metric_choice in asset_options else asset_options[0]
                            )
                        st.selectbox(
                            "Assets",
                            options=asset_options,
                            key=asset_pick_key,
                            label_visibility="collapsed",
                        )
                        c1, c2 = st.columns(2, gap="small")
                        with c1:
                            st.button("Cancel", key=asset_cancel_key, use_container_width=True)
                        with c2:
                            if st.button("Apply", key=asset_apply_key, use_container_width=True):
                                st.session_state["ytd_metric"] = st.session_state[asset_pick_key]
                                st.rerun()
                    else:
                        st.info("No assets available in this category.")
            else:
                st.selectbox(
                    "Price Or Metric",
                    options=metric_options,
                    index=metric_options.index(metric_choice),
                    label_visibility="collapsed",
                    key="ytd_metric",
                )

        with filter_cols[1]:
            st.markdown('<div class="charts-filter-label">Add Average</div>', unsafe_allow_html=True)
            if popover_fn:
                with popover_fn("Add Average"):
                    st.multiselect(
                        "Years",
                        options=year_options,
                        key=custom_pick_key,
                        placeholder="Select years",
                    )
                    if st.button("Add Custom Series", key=custom_add_btn_key, use_container_width=True):
                        picked = tuple(sorted(int(y) for y in st.session_state.get(custom_pick_key, [])))
                        if picked:
                            st.session_state[custom_series_key] = picked
                            st.rerun()
                        else:
                            st.info("Select at least one year.")
                    st.caption("Pre-Configured Averages")
                    for avg_key, _ in AVG_OPTIONS:
                        label = _avg_option_label(avg_key, ytd_df, current_year)
                        if st.checkbox(label, value=False, key=f"{state_prefix}_avg_{avg_key}"):
                            selected_avg_keys.append(avg_key)
            else:
                with st.expander("Add Average", expanded=False):
                    st.multiselect(
                        "Years",
                        options=year_options,
                        key=custom_pick_key,
                        placeholder="Select years",
                    )
                    if st.button("Add Custom Series", key=custom_add_btn_key, use_container_width=True):
                        picked = tuple(sorted(int(y) for y in st.session_state.get(custom_pick_key, [])))
                        if picked:
                            st.session_state[custom_series_key] = picked
                            st.rerun()
                        else:
                            st.info("Select at least one year.")
                    st.caption("Pre-Configured Averages")
                    for avg_key, _ in AVG_OPTIONS:
                        label = _avg_option_label(avg_key, ytd_df, current_year)
                        if st.checkbox(label, value=False, key=f"{state_prefix}_avg_{avg_key}"):
                            selected_avg_keys.append(avg_key)

        with filter_cols[2]:
            st.markdown('<div class="charts-filter-label">Standard Deviation</div>', unsafe_allow_html=True)
            std_button_label = _selected_years_short_label(current_std, "Standard Deviation")
            if popover_fn:
                with popover_fn(std_button_label):
                    st.multiselect(
                        "Years",
                        options=year_options,
                        key=std_pick_key,
                        placeholder="Select years",
                    )
                    if st.button("Apply Standard Deviation", key=std_add_btn_key, use_container_width=True):
                        picked = tuple(sorted(int(y) for y in st.session_state.get(std_pick_key, [])))
                        if picked:
                            st.session_state[std_series_key] = picked
                            st.rerun()
                        else:
                            st.info("Select at least one year.")
            else:
                with st.expander("Standard Deviation", expanded=False):
                    st.multiselect(
                        "Years",
                        options=year_options,
                        key=std_pick_key,
                        placeholder="Select years",
                    )
                    if st.button("Apply Standard Deviation", key=std_add_btn_key, use_container_width=True):
                        picked = tuple(sorted(int(y) for y in st.session_state.get(std_pick_key, [])))
                        if picked:
                            st.session_state[std_series_key] = picked
                            st.rerun()
                        else:
                            st.info("Select at least one year.")

        with filter_cols[3]:
            st.markdown('<div class="charts-filter-label">SD Multiplier</div>', unsafe_allow_html=True)
            sd_multiplier = st.selectbox(
                "SD Multiplier",
                options=[1, 2, 3, 4, 5],
                index=[1, 2, 3, 4, 5].index(int(st.session_state.get(sd_multiplier_key, 1))),
                key=sd_multiplier_key,
                label_visibility="collapsed",
            )

        with filter_cols[4]:
            st.markdown('<div class="charts-filter-label">ROI Scale</div>', unsafe_allow_html=True)
            scale_choice = st.radio(
                "ROI Scale",
                options=["Linear", "Logarithmic"],
                horizontal=True,
                key=scale_key,
                label_visibility="collapsed",
            )

    fig = go.Figure()

    # ── Year traces ──────────────────────────────────────────────────────────────
    for year in years:
        year_df = ytd_df[ytd_df["year"] == year]
        if year_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=year_df["day"],
                y=year_df["roi"],
                mode="lines",
                name=str(year),
                visible=True,
                uid=f"{metric_key}_ytd_year_{year}",
                line=dict(color=_series_color(year), width=1.4),
                customdata=year_df["date"],
                hovertemplate=(
                    f"{year} ROI: %{{y:.3f}} "
                    "(%{customdata|%Y-%m-%d})<extra></extra>"
                ),
            )
        )

    # ── Average traces ───────────────────────────────────────────────────────────
    for avg_key in selected_avg_keys:
        avg_label = next((lbl for k, lbl in AVG_OPTIONS if k == avg_key), avg_key)
        avg_df = _compute_average_series(ytd_df, avg_key, current_year)
        if avg_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=avg_df["day"],
                y=avg_df["roi"],
                mode="lines",
                name=avg_label,
                visible=True,
                uid=f"{metric_key}_ytd_avg_{avg_key}",
                line=dict(
                    color=_AVG_LINE_COLORS.get(avg_key, "#e6e9ef"),
                    width=1.4,
                    dash="solid",
                ),
                hovertemplate=f"{avg_label}: %{{y:.3f}}<extra></extra>",
            )
        )

    custom_years = tuple(st.session_state.get(custom_series_key, tuple()))
    if custom_years:
        custom_df = _compute_custom_average_series(ytd_df, custom_years)
        if not custom_df.empty:
            custom_label = _custom_series_label(custom_years)
            custom_uid = f"{metric_key}_ytd_avg_custom_" + "_".join(str(y) for y in custom_years)
            fig.add_trace(
                go.Scatter(
                    x=custom_df["day"],
                    y=custom_df["roi"],
                    mode="lines",
                    name=custom_label,
                    visible=True,
                    uid=custom_uid,
                    line=dict(
                        color="#fbbf24",
                        width=1.8,
                        dash="solid",
                    ),
                    hovertemplate=f"{custom_label}: %{{y:.3f}}<extra></extra>",
                )
            )

    std_years = tuple(st.session_state.get(std_series_key, tuple()))
    if std_years:
        std_df = _compute_custom_std_band(ytd_df, std_years)
        if not std_df.empty:
            std_label = _std_series_label(std_years)
            std_uid = f"{metric_key}_ytd_std_" + "_".join(str(y) for y in std_years)
            std_multiplier = int(sd_multiplier)
            std_band = (std_df["std"] * std_multiplier).clip(lower=0.0)
            lower_band = (std_df["mean"] - std_band).clip(lower=1e-4)
            upper_band = (std_df["mean"] + std_band).clip(lower=1e-4)
            upper_band = pd.Series(
                np.maximum(upper_band.to_numpy(), (lower_band * 1.0001).to_numpy()),
                index=std_df.index,
            )
            std_display_label = std_label if std_multiplier == 1 else f"{std_label} x{std_multiplier}"

            fig.add_trace(
                go.Scatter(
                    x=std_df["day"],
                    y=lower_band,
                    mode="lines",
                    line=dict(width=1.0, color="rgba(229, 231, 235, 0.45)"),
                    name=f"{std_display_label} lower",
                    showlegend=False,
                    legendgroup=std_uid,
                    hoverinfo="skip",
                    uid=f"{std_uid}_lower",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=std_df["day"],
                    y=upper_band,
                    mode="lines",
                    line=dict(width=1.0, color="rgba(229, 231, 235, 0.55)"),
                    fill="tonexty",
                    fillcolor="rgba(203, 213, 225, 0.28)",
                    name=f"{std_display_label} band",
                    showlegend=False,
                    legendgroup=std_uid,
                    hoverinfo="skip",
                    uid=f"{std_uid}_upper",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=std_df["day"],
                    y=std_df["mean"],
                    mode="lines",
                    name=std_display_label,
                    visible=True,
                    uid=f"{std_uid}_mean",
                    legendgroup=std_uid,
                    line=dict(color="#e5e7eb", width=1.7),
                    customdata=np.column_stack(
                        [
                            std_df["mean"].to_numpy(),
                            lower_band.to_numpy(),
                            upper_band.to_numpy(),
                            std_band.to_numpy(),
                        ]
                    ),
                    hovertemplate=(
                        f"{std_display_label}<br>"
                        "Average: %{customdata[0]:.3f}<br>"
                        "Lower SD: %{customdata[1]:.3f}<br>"
                        "Upper SD: %{customdata[2]:.3f}<br>"
                        "Standard Deviation: %{customdata[3]:.3f}<extra></extra>"
                    ),
                )
            )

    # ── Show / Hide All ──────────────────────────────────────────────────────────
    trace_count = len(fig.data)
    LEGEND_X_POS = 0.5

    fig.update_layout(
        height=720,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=30, r=20, t=10, b=150),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6e9ef", size=13),
        dragmode="zoom",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.13,
            xanchor="center",
            x=LEGEND_X_POS,
            font=dict(color="#e6e9ef", size=13),
            itemclick="toggle",
            itemdoubleclick="toggleothers",
            groupclick="togglegroup",
        ),
        hoverlabel=dict(
            bgcolor="#0b0f14",
            bordercolor="rgba(96, 165, 250, 0.4)",
            font=dict(color="#e6e9ef"),
        ),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                showactive=False,
                x=0.0,
                y=-0.24,
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(0,0,0,0)",
                borderwidth=0,
                pad=dict(l=0, r=0, t=0, b=0),
                font=dict(color="#e6e9ef", size=13),
                buttons=[
                    dict(
                        label="● Show / Hide All",
                        method="restyle",
                        args=[{"visible": ["legendonly"] * trace_count}],
                        args2=[{"visible": [True] * trace_count}],
                    )
                ],
            )
        ],
        uirevision=f"{metric_key}-ytd-roi",
    )

    fig.update_xaxes(
        title_text="Days Of The Year",
        showgrid=False,
        zeroline=False,
        range=[0, 366],
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikecolor="rgba(255,255,255,0.5)",
        spikethickness=0.4,
    )
    fig.update_yaxes(
        title_text="ROI (x)",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=True,
        zerolinecolor="rgba(255,255,255,0.25)",
        type="log" if scale_choice == "Logarithmic" else "linear",
    )

    with st.container(border=True):
        st.plotly_chart(
            fig,
            use_container_width=True,
            key="ytd_roi_plot",
            config={
                "displayModeBar": False,
                "scrollZoom": False,
                "doubleClick": "reset",
                "showTips": False,
                "responsive": True,
            },
        )

    st.markdown(
        f"""
        <div class="charts-description">
          <h4>Description</h4>
          <p>
            This chart shows the Year-To-Date return on investment (ROI) for {asset_name}.
            ROI is calculated by dividing the asset price at any point in a year by the
            asset price on January 1st of that same year.
          </p>
          <p>
            For example, an ROI value of 0.4 means {asset_name} is down 60% versus January 1st.
            Each line represents one year from {_METRIC_CONFIG[metric_choice]["min_year"]} through the current year.
          </p>
          <h4>Usage</h4>
          <p>
            Use this chart to compare seasonal and cycle-driven behavior across calendar years.
            The Add Average filter helps compare current behavior against election-cycle groups
            and full-history annual tendencies while keeping year-by-year lines visible.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
