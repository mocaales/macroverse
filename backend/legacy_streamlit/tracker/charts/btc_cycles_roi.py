import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import fetch_btc_prices


BTC_CYCLE_SPECS = [
    {"label": "Market Cycle 1", "start": "2010-07-18", "end": "2011-06-08"},
    {"label": "Market Cycle 2", "start": "2011-11-18", "end": "2013-12-04"},
    {"label": "Market Cycle 3", "start": "2015-01-14", "end": "2017-12-17"},
    {"label": "Market Cycle 4", "start": "2018-12-15", "end": "2021-11-10"},
    {"label": "Market Cycle 5", "start": "2022-11-21", "end": "2025-10-06"},
]


def _btc_cycle_roi_series(df, mode="to_peak"):
    if df.empty:
        return pd.DataFrame()
    df = df.sort_values("date").dropna(subset=["price"]).copy().reset_index(drop=True)
    dates = pd.to_datetime(df["date"]).to_numpy()

    def _row_on_or_after(target_date):
        if not target_date:
            return None
        target = pd.to_datetime(target_date)
        idx = np.searchsorted(dates, np.datetime64(target), side="left")
        if idx >= len(df):
            return None
        row = df.iloc[idx]
        price_val = pd.to_numeric(row["price"], errors="coerce")
        if not np.isfinite(price_val) or price_val <= 0:
            return None
        return {"date": row["date"], "price": float(price_val)}

    bottoms = [_row_on_or_after(spec["start"]) for spec in BTC_CYCLE_SPECS]
    peaks = [_row_on_or_after(spec["end"]) for spec in BTC_CYCLE_SPECS]

    cycles = []
    cycle_dates = {}
    for idx, spec in enumerate(BTC_CYCLE_SPECS):
        bottom = bottoms[idx]
        if not bottom:
            continue
        start = bottom["date"]
        peak = peaks[idx]
        if mode == "to_bottom":
            next_bottom = bottoms[idx + 1] if idx + 1 < len(bottoms) else None
            end = next_bottom["date"] if next_bottom else df["date"].max()
        else:
            end = peak["date"] if peak else df["date"].max()
        if start >= end:
            continue
        cycle_dates[spec["label"]] = {
            "start": start,
            "end": end,
            "bottom": bottom.get("date"),
            "peak": peak.get("date") if peak else None,
        }
        cycle_df = df[(df["date"] >= start) & (df["date"] <= end)].copy()
        if cycle_df.empty:
            continue
        bottom_price = bottom["price"]
        if not np.isfinite(bottom_price) or bottom_price <= 0:
            continue
        cycle_df["day"] = (cycle_df["date"] - start).dt.days
        cycle_df["roi"] = cycle_df["price"] / bottom_price
        cycle_df["roi"] = cycle_df["roi"].replace([np.inf, -np.inf], np.nan)
        cycle_df = cycle_df.dropna(subset=["roi"])
        cycle_df["roi"] = cycle_df["roi"].clip(lower=1)
        if cycle_df.empty:
            continue
        cycle_df["cycle"] = spec["label"]
        cycle_df["hover_date"] = cycle_df["date"]
        cycles.append(cycle_df[["day", "roi", "cycle", "hover_date"]])

    if not cycles:
        return pd.DataFrame()
    result = pd.concat(cycles, ignore_index=True)
    result.attrs["cycle_dates"] = cycle_dates
    return result


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cycle_roi(mode):
    df = fetch_btc_prices()
    if df.empty:
        return pd.DataFrame()
    return _btc_cycle_roi_series(df, mode=mode)


def render(context):
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    btc_df = fetch_btc_prices()
    if btc_df.empty:
        st.error("BTC price data is unavailable. Install yfinance or check your connection.")
        return

    header_container = st.container()

    st.markdown('<div id="charts-filters"></div>', unsafe_allow_html=True)
    filter_cols = st.columns([1, 2], gap="small")
    with filter_cols[0]:
        st.markdown(
            '<div class="charts-filter-label">Cycle Window</div>',
            unsafe_allow_html=True,
        )
        roi_mode_label = st.selectbox(
            "Cycle Window",
            options=["To peak", "To bottom"],
            index=0,
            label_visibility="collapsed",
        )

    roi_mode = "to_peak" if roi_mode_label == "To peak" else "to_bottom"
    roi_df = _cached_cycle_roi(roi_mode)
    if roi_df.empty:
        st.warning("Not enough BTC history to compute cycle ROI.")
        return
    cycle_count = roi_df["cycle"].nunique()
    if cycle_count < 5:
        st.caption(f"Only {cycle_count} cycles available based on current BTC history sources.")

    fig = go.Figure()
    palette = ["#60a5fa", "#f87171", "#f59e0b", "#22c55e", "#a855f7"]
    cycles_sorted = [
        spec["label"]
        for spec in BTC_CYCLE_SPECS
        if spec["label"] in roi_df["cycle"].unique()
    ]
    for idx, cycle in enumerate(cycles_sorted):
        cycle_df = roi_df[roi_df["cycle"] == cycle]
        fig.add_trace(
            go.Scatter(
                x=cycle_df["day"],
                y=cycle_df["roi"],
                customdata=cycle_df["hover_date"],
                mode="lines",
                name=cycle,
                line=dict(color=palette[idx % len(palette)], width=1.6),
                hovertemplate=(
                    f"{cycle} ROI: %{{y:.2f}} "
                    "(%{customdata|%Y-%m-%d})<extra></extra>"
                ),
            )
        )

    roi_clean = roi_df["roi"].replace([np.inf, -np.inf], np.nan).dropna()
    peak_roi = roi_clean.max() if not roi_clean.empty else 0.0
    mode_suffix = "To Peak" if roi_mode == "to_peak" else "To Bottom"
    with header_container:
        header_cols = st.columns([6, 1], gap="small")
        with header_cols[0]:
            st.markdown(
                f"""
                <div class="charts-header">
                  <h3>Bitcoin ROI After Cycle Bottom</h3>
                  <div class="charts-meta">Cycle bottom: {peak_roi:.3f} ({mode_suffix})</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            is_fav = "Bitcoin ROI After Cycle Bottom" in favourites
            fav_label = "Favourites" if is_fav else "Favourite"
            st.markdown(
                f'<div class="charts-filter-label">{fav_label}</div>',
                unsafe_allow_html=True,
            )
            if toggle_favourite:
                toggle_favourite("Bitcoin ROI After Cycle Bottom", "btc_cycles")

    fig.update_layout(
        height=700,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=30, r=20, t=10, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6e9ef", size=13),
        dragmode="zoom",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="left",
            x=0.0,
            font=dict(color="#e6e9ef"),
        ),
        hoverlabel=dict(
            bgcolor="#0b0f14",
            bordercolor="rgba(96, 165, 250, 0.4)",
            font=dict(color="#e6e9ef"),
        ),
        uirevision="bitcoin-cycles-roi",
    )
    fig.update_xaxes(
        title_text="Days Since Market Cycle Bottom",
        showgrid=False,
        zeroline=False,
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
        type="log",
        tickmode="array",
        tickvals=[0.4, 1, 2, 4, 10, 20, 40, 100, 200, 400],
        range=[-0.4, 2.7],
    )

    with st.container(border=True):
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False,
                "scrollZoom": False,
                "doubleClick": "reset",
                "showTips": False,
                "responsive": True,
            },
        )

    if roi_mode == "to_peak":
        description_html = """
        <div class="charts-description">
          <h4>Description</h4>
          <p>
            This chart shows the return on investment (ROI) for each Bitcoin market
            cycle measured from its cycle bottom to its cycle peak. The cycle bottom
            is taken from the specified bottom date for each cycle.
          </p>
          <p>
            ROI is calculated as price divided by the cycle bottom. An ROI value of 2
            means Bitcoin appreciated 100% from the cycle bottom. The series is clipped
            so ROI does not fall below 1 in this view, keeping the focus on upside
            performance within each cycle.
          </p>
        </div>
        """
    else:
        description_html = """
        <div class="charts-description">
          <h4>Description</h4>
          <p>
            This chart shows the return on investment (ROI) for each Bitcoin market
            cycle from the cycle bottom through the subsequent cycle bottom. The cycle
            bottom is taken from the specified bottom date for each cycle.
          </p>
          <p>
            ROI is calculated as price divided by the cycle bottom. An ROI value of 2
            means Bitcoin appreciated 100% from the cycle bottom. The series is clipped
            so ROI does not fall below 1 in this view, highlighting the full rise and
            drawdown within each cycle.
          </p>
        </div>
        """

    st.markdown(description_html, unsafe_allow_html=True)
