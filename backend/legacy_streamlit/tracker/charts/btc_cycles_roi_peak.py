import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import fetch_btc_prices


BTC_CYCLE_SPECS = [
    {"label": "Peak 1 - Bottom 2", "peak": "2011-06-08", "bottom": "2011-11-18"},
    {"label": "Peak 2 - Bottom 3", "peak": "2013-12-04", "bottom": "2015-01-14"},
    {"label": "Peak 3 - Bottom 4", "peak": "2017-12-17", "bottom": "2018-12-15"},
    {"label": "Peak 4 - Bottom 5", "peak": "2021-11-10", "bottom": "2022-11-21"},
    {"label": "Peak 5 - Bottom 6", "peak": "2025-10-06", "bottom": None},
]


def _btc_cycle_roi_peak_series(df):
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

    peaks = [_row_on_or_after(spec["peak"]) for spec in BTC_CYCLE_SPECS]
    bottoms = [_row_on_or_after(spec.get("bottom")) for spec in BTC_CYCLE_SPECS]

    cycles = []
    for idx, spec in enumerate(BTC_CYCLE_SPECS):
        peak = peaks[idx]
        if not peak:
            continue
        start = peak["date"]
        bottom = bottoms[idx]
        end = bottom["date"] if bottom else df["date"].max()
        if start >= end:
            continue
        cycle_df = df[(df["date"] >= start) & (df["date"] <= end)].copy()
        if cycle_df.empty:
            continue
        peak_price = peak["price"]
        if not np.isfinite(peak_price) or peak_price <= 0:
            continue
        cycle_df["day"] = (cycle_df["date"] - start).dt.days
        cycle_df["roi"] = cycle_df["price"] / peak_price
        cycle_df["roi"] = cycle_df["roi"].replace([np.inf, -np.inf], np.nan)
        cycle_df = cycle_df.dropna(subset=["roi"])
        if cycle_df.empty:
            continue
        cycle_df["cycle"] = spec["label"]
        cycle_df["hover_date"] = cycle_df["date"]
        cycles.append(cycle_df[["day", "roi", "cycle", "hover_date"]])

    if not cycles:
        return pd.DataFrame()
    return pd.concat(cycles, ignore_index=True)


def _spec_key():
    return tuple(
        (spec["label"], spec["peak"], spec.get("bottom"))
        for spec in BTC_CYCLE_SPECS
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_peak_roi(spec_key):
    df = fetch_btc_prices()
    if df.empty:
        return pd.DataFrame()
    return _btc_cycle_roi_peak_series(df)


def render(context):
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    roi_df = _cached_peak_roi(_spec_key())
    if roi_df.empty:
        st.error("BTC price data is unavailable. Install yfinance or check your connection.")
        return

    header_cols = st.columns([6, 1], gap="small")
    with header_cols[0]:
        current_label = BTC_CYCLE_SPECS[-1]["label"] if BTC_CYCLE_SPECS else None
        current_value = None
        if current_label:
            current_series = roi_df[roi_df["cycle"] == current_label]
            if not current_series.empty:
                current_series = current_series.sort_values("day")
                current_value = current_series["roi"].iloc[-1]
        current_text = "—" if current_value is None else f"{current_value:.3f}"

        st.markdown(
            f"""
            <div class="charts-header">
              <h3>Bitcoin ROI After Cycle Peak</h3>
              <div class="charts-meta">ROI of the current cycle peak: {current_text} (to bottom)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        is_fav = "Bitcoin ROI After Cycle Peak" in favourites
        fav_label = "Favourites" if is_fav else "Favourite"
        st.markdown(
            f'<div class="charts-filter-label">{fav_label}</div>',
            unsafe_allow_html=True,
        )
        if toggle_favourite:
            toggle_favourite("Bitcoin ROI After Cycle Peak", "btc_cycles_peak")

    all_cycles = [
        spec["label"]
        for spec in BTC_CYCLE_SPECS
        if spec["label"] in roi_df["cycle"].unique()
    ]
    if not all_cycles:
        all_cycles = list(roi_df["cycle"].unique())
    plot_df = roi_df

    fig = go.Figure()
    palette = ["#60a5fa", "#f87171", "#f59e0b", "#22c55e", "#a855f7"]
    for idx, cycle in enumerate(all_cycles):
        cycle_df = plot_df[plot_df["cycle"] == cycle]
        if cycle_df.empty:
            continue
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
        uirevision="bitcoin-cycles-peak-roi",
    )
    fig.update_xaxes(
        title_text="Days Since Peak",
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
        tickvals=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1],
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

    # Cycle filter removed per request.

    st.markdown(
        """
        <div class="charts-description">
          <h4>Description</h4>
          <p>
            This chart shows the return on investments (ROI) for all market cycles overlaid
            from peak to bottom. The ROI value is calculated by dividing its current price by
            the price at its previous peak.
          </p>
          <p>
            For example, if the ROI value is 0.5 then Bitcoin has lost 50% value from its
            most recent peak. Note that the ROI value must go below 1 at the start in this
            chart or else we would not have picked the correct peak price.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
