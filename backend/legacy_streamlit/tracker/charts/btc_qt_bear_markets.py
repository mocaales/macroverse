import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import fetch_btc_prices


QT_CYCLES = [
    {"label": "2019 (Jun 26)", "start": "2019-06-26", "end": "2020-03-13"},
    {"label": "2025 (Oct 6)", "start": "2025-10-06", "end": None},
]


def _spec_key():
    return tuple((spec["label"], spec["start"], spec.get("end")) for spec in QT_CYCLES)


def _qt_roi_series(df):
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

    cycles = []
    for spec in QT_CYCLES:
        start_row = _row_on_or_after(spec["start"])
        if not start_row:
            continue
        end_row = _row_on_or_after(spec.get("end"))
        start_date = start_row["date"]
        end_date = end_row["date"] if end_row else df["date"].max()
        if start_date >= end_date:
            continue
        cycle_df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
        if cycle_df.empty:
            continue
        peak_price = start_row["price"]
        if not np.isfinite(peak_price) or peak_price <= 0:
            continue
        cycle_df["day"] = (cycle_df["date"] - start_date).dt.days
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


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_qt_roi(spec_key):
    df = fetch_btc_prices()
    if df.empty:
        return pd.DataFrame()
    return _qt_roi_series(df)


def render(context):
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    roi_df = _cached_qt_roi(_spec_key())
    if roi_df.empty:
        st.error("BTC price data is unavailable. Install yfinance or check your connection.")
        return

    header_cols = st.columns([6, 1], gap="small")
    with header_cols[0]:
        current_label = QT_CYCLES[-1]["label"] if QT_CYCLES else None
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
              <h3>QT Ending Bear Markets</h3>
              <div class="charts-meta">Peak: {current_text} (To Bottom)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        is_fav = "QT Ending Bear Markets" in favourites
        fav_label = "Favourites" if is_fav else "Favourite"
        st.markdown(
            f'<div class="charts-filter-label">{fav_label}</div>',
            unsafe_allow_html=True,
        )
        if toggle_favourite:
            toggle_favourite("QT Ending Bear Markets", "qt_bear_markets")

    cycles = [
        spec["label"]
        for spec in QT_CYCLES
        if spec["label"] in roi_df["cycle"].unique()
    ]
    if not cycles:
        cycles = list(roi_df["cycle"].unique())

    fig = go.Figure()
    palette = ["#60a5fa", "#f87171", "#f59e0b", "#22c55e"]
    for idx, cycle in enumerate(cycles):
        cycle_df = roi_df[roi_df["cycle"] == cycle]
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
        uirevision="qt-ending-bear-markets",
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

    st.markdown(
        """
        <div class="charts-description">
          <h4>Description</h4>
          <p>
            This chart compares Bitcoin bear markets that coincided with the end of
            Federal Reserve Quantitative Tightening (QT). Each series starts at the
            QT bear-market peak (ROI = 1) and tracks the drawdown into the subsequent bottom.
          </p>
          <p>
            QT is when the Fed reduces its balance sheet by letting assets roll off or
            selling them outright, tightening monetary conditions. When QT ends, it can
            signal a shift toward easier policy and changing risk appetite.
          </p>
          <h4>Usage</h4>
          <p>
            Use this chart to compare the depth and duration of drawdowns after QT peaks,
            and to contextualize how the current cycle is evolving versus prior QT-related
            bear markets.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
