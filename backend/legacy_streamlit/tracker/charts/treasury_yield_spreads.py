import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import FRED_SERIES, fetch_fred_series, fetch_sp500_overlay, _merge_series, _to_daily


RATE_OF_CHANGE_PERIODS = {
    "DoD": 1,
    "WoW": 5,
    "MoM": 21,
    "QoQ": 63,
    "YoY": 252,
}

MOVING_AVERAGE_WINDOWS = {
    "7D SMA": 7,
    "30D SMA": 30,
    "90D SMA": 90,
}


@st.cache_data(show_spinner=False, ttl=3600)
def _load_spread_data(long_choice, short_choice, roc_choice, ma_choice, overlay_choice, api_key):
    long_series = FRED_SERIES.get(long_choice)
    short_series = FRED_SERIES.get(short_choice)
    if not long_series or not short_series:
        return {}

    long_df = fetch_fred_series(long_series, api_key)
    short_df = fetch_fred_series(short_series, api_key)
    if long_choice == "10Y":
        long_df = _merge_series(long_df, fetch_fred_series("GS10", api_key))
    if short_choice == "3M":
        short_df = _merge_series(short_df, fetch_fred_series("TB3MS", api_key))

    long_df = _to_daily(long_df).rename(columns={"value": "long"})
    short_df = _to_daily(short_df).rename(columns={"value": "short"})

    spread_df = long_df.merge(short_df, on="date", how="inner")
    if spread_df.empty:
        return {}

    spread_df["spread_base"] = spread_df["long"] - spread_df["short"]
    spread_df["spread"] = spread_df["spread_base"]
    spread_base_df = spread_df[["date", "spread_base"]].copy()
    spread_df["spread"] = _apply_rate_of_change(spread_df["spread"], roc_choice)
    spread_df["spread"] = _apply_moving_average(spread_df["spread"], ma_choice)
    spread_df = spread_df.dropna(subset=["spread"])
    if spread_df.empty:
        return {}

    overlay_df = pd.DataFrame()
    overlay_source = ""
    if overlay_choice != "None":
        overlay_df = fetch_sp500_overlay()
        if not overlay_df.empty:
            overlay_source = "Yahoo Finance"
        else:
            overlay_df = fetch_fred_series("SP500", api_key).rename(columns={"value": "overlay"})
            overlay_source = "FRED (10y)"
    if not overlay_df.empty and "overlay" not in overlay_df.columns:
        overlay_df = pd.DataFrame()

    min_date = spread_base_df["date"].min()
    max_date = spread_df["date"].max()

    overlay_trim = pd.DataFrame()
    shapes = []
    overlay_active = False
    if overlay_choice != "None" and not overlay_df.empty:
        overlay_trim = overlay_df.copy()
        overlay_trim = overlay_trim[
            (overlay_trim["date"] >= min_date) & (overlay_trim["date"] <= max_date)
        ]
        if not overlay_trim.empty:
            overlay_active = True
            shapes = _spread_to_spx_shapes(spread_base_df, overlay_trim, min_days=120)

    return {
        "spread_df": spread_df,
        "spread_base_df": spread_base_df,
        "overlay_trim": overlay_trim,
        "overlay_source": overlay_source,
        "min_date": min_date,
        "max_date": max_date,
        "overlay_active": overlay_active,
        "shapes": shapes,
    }


def _apply_rate_of_change(series, roc_choice):
    if roc_choice == "None":
        return series
    periods = RATE_OF_CHANGE_PERIODS.get(roc_choice)
    if not periods:
        return series
    return series.diff(periods)


def _apply_moving_average(series, ma_choice):
    if ma_choice == "None":
        return series
    window = MOVING_AVERAGE_WINDOWS.get(ma_choice)
    if not window:
        return series
    return series.rolling(window=window, min_periods=1).mean()


def _spread_to_spx_shapes(spread_df, overlay_df, min_days=90):
    if (
        spread_df.empty
        or overlay_df.empty
        or "spread_base" not in spread_df.columns
        or "overlay" not in overlay_df.columns
    ):
        return []

    spread = spread_df[["date", "spread_base"]].dropna().sort_values("date").copy()
    overlay = overlay_df[["date", "overlay"]].dropna().sort_values("date").copy()

    spread_idx = spread.set_index("date")
    overlay_idx = overlay.set_index("date")
    aligned_spread = spread_idx.reindex(overlay_idx.index).ffill()

    series = aligned_spread["spread_base"]
    cross = (series > 0) & (series.shift(1) <= 0)
    cross_dates = series.index[cross.fillna(False)]

    shapes = []
    for cross_dt in cross_dates:
        window = series.loc[cross_dt:]
        neg_idx = window[window < 0].index
        window_end = neg_idx[0] if len(neg_idx) else series.index[-1]

        overlay_window = overlay_idx.loc[cross_dt:window_end]
        if overlay_window.empty:
            continue
        trough_dt = overlay_window["overlay"].idxmin()
        if trough_dt <= cross_dt:
            continue
        if (trough_dt - cross_dt).days < min_days:
            continue
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=cross_dt,
                x1=trough_dt,
                y0=0,
                y1=1,
                fillcolor="rgba(255,255,255,0.08)",
                line=dict(width=0),
                layer="below",
            )
        )
    return shapes


def render(context):
    api_key = context.get("api_key")
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    if not api_key:
        st.error("Missing FRED_API_KEY. Set it in your .env or Streamlit secrets.")
        return

    header_container = st.container()

    with st.container(border=True):
        st.markdown('<div id="charts-filters"></div>', unsafe_allow_html=True)
        filter_cols = st.columns([1, 1, 1.8, 1, 1], gap="small")
        with filter_cols[0]:
            st.markdown(
                '<div class="charts-filter-label">Interest Rate A</div>',
                unsafe_allow_html=True,
            )
            long_choice = st.selectbox(
                "Interest Rate A",
                options=["30Y", "10Y", "5Y", "2Y", "1Y"],
                index=1,
                label_visibility="collapsed",
            )
        with filter_cols[1]:
            st.markdown(
                '<div class="charts-filter-label">Interest Rate B</div>',
                unsafe_allow_html=True,
            )
            short_choice = st.selectbox(
                "Interest Rate B",
                options=["3M", "6M", "1Y", "2Y"],
                index=0,
                label_visibility="collapsed",
            )
        with filter_cols[2]:
            st.markdown(
                '<div class="charts-filter-label">Rate of Change</div>',
                unsafe_allow_html=True,
            )
            roc_choice = st.radio(
                "Rate of Change",
                options=["None", "DoD", "WoW", "MoM", "QoQ", "YoY"],
                horizontal=True,
                label_visibility="collapsed",
            )
        with filter_cols[3]:
            st.markdown(
                '<div class="charts-filter-label">Moving Average</div>',
                unsafe_allow_html=True,
            )
            ma_choice = st.selectbox(
                "Moving Average",
                options=["None", "7D SMA", "30D SMA", "90D SMA"],
                index=0,
                label_visibility="collapsed",
            )
        with filter_cols[4]:
            st.markdown(
                '<div class="charts-filter-label">Overlay</div>',
                unsafe_allow_html=True,
            )
            overlay_choice = st.selectbox(
                "Overlay",
                options=["None", "GSPC (S&P 500 Index)"],
                index=0,
                label_visibility="collapsed",
            )

    data = _load_spread_data(
        long_choice,
        short_choice,
        roc_choice,
        ma_choice,
        overlay_choice,
        api_key,
    )
    if not data:
        st.warning("No data returned for the selected maturities.")
        return

    spread_df = data["spread_df"]
    spread_base_df = data["spread_base_df"]
    overlay_trim = data["overlay_trim"]
    overlay_source = data["overlay_source"]
    min_date = data["min_date"]
    max_date = data["max_date"]
    overlay_active = data["overlay_active"]
    shapes = data["shapes"]

    latest_date = spread_df["date"].max()
    last_stamp = latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else "—"
    latest_val = spread_df["spread"].iloc[-1] if not spread_df.empty else 0.0
    label_suffix = "Daily, Percentage"
    if roc_choice != "None":
        label_suffix = f"{roc_choice} Change (pp)"
    y_axis_label = "Spread (pp)" if roc_choice == "None" else f"{roc_choice} Change (pp)"
    hover_metric = "Spread" if roc_choice == "None" else "Change"
    overlay_meta = ""
    if overlay_choice != "None" and overlay_source:
        overlay_meta = f" • Overlay: S&P 500 ({overlay_source})"

    with header_container:
        header_cols = st.columns([6, 1], gap="small")
        with header_cols[0]:
            st.markdown(
                f"""
                <div class="charts-header">
                  <h3>Spread: {long_choice} - {short_choice} ({label_suffix})</h3>
                  <div class="charts-meta">Updated: {last_stamp} • Latest: {latest_val:+.2f} • Source: FRED{overlay_meta}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            is_fav = "Treasury Yield Spreads" in favourites
            fav_label = "Favourites" if is_fav else "Favourite"
            st.markdown(
                f'<div class="charts-filter-label">{fav_label}</div>',
                unsafe_allow_html=True,
            )
            if toggle_favourite:
                toggle_favourite("Treasury Yield Spreads", "treasury_spreads")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=spread_df["date"],
            y=spread_df["spread"],
            mode="lines",
            name=f"Treasury Yield Spread: {long_choice} - {short_choice}",
            line=dict(color="#f87171", width=1.8, shape="spline", smoothing=1.1),
            fill="tozeroy",
            fillcolor="rgba(248, 113, 113, 0.35)",
            hovertemplate=(
                "<b>%{x|%d %b %Y}</b><br>"
                f"{hover_metric} {long_choice} - {short_choice}: %{{y:.2f}} pp<extra></extra>"
            ),
        )
    )

    if overlay_choice != "None" and not overlay_trim.empty:
        fig.add_trace(
            go.Scatter(
                x=overlay_trim["date"],
                y=overlay_trim["overlay"],
                mode="lines",
                name="GSPC (S&P 500 Index)",
                line=dict(color="#60a5fa", width=1.2),
                yaxis="y2",
                hovertemplate="S&P 500: %{y:,.0f}<extra></extra>",
            )
        )
    if shapes:
        fig.add_trace(
            go.Scatter(
                x=[],
                y=[],
                mode="lines",
                name="Spread-to-Trough Window",
                line=dict(color="rgba(255,255,255,0.45)", width=10),
                showlegend=True,
                hoverinfo="skip",
            )
        )

    yaxis2_cfg = dict(
        overlaying="y",
        side="right",
        showgrid=False,
        title="S&P 500",
        title_font=dict(size=12),
        tickfont=dict(size=11),
        visible=overlay_active,
        type="log" if overlay_active else "linear",
    )

    fig.update_layout(
        height=720,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=30, r=30, t=10, b=60),
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
            bordercolor="rgba(248, 113, 113, 0.4)",
            font=dict(color="#e6e9ef"),
        ),
        shapes=shapes,
        uirevision="treasury-yield-spreads",
        yaxis2=yaxis2_cfg,
    )
    fig.update_yaxes(
        title_text=y_axis_label,
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=True,
        zerolinecolor="rgba(255,255,255,0.25)",
        title_font=dict(size=14),
        tickfont=dict(size=12),
    )
    fig.update_xaxes(
        title_text="Date",
        showgrid=False,
        zeroline=False,
        tickformat="%Y",
        range=[min_date, max_date],
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(248, 113, 113, 0.35)",
        spikethickness=1,
        title_font=dict(size=14),
        tickfont=dict(size=12),
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
            Treasury yield spreads are computed from Constant Maturity Treasury Rates.
            Subtracting a short-maturity yield from a long-maturity yield isolates the
            term structure slope, which embeds expectations for growth, inflation, and
            future policy rates. A negative spread (curve inversion) means long rates
            have fallen below short rates, a pattern historically associated with
            tighter financial conditions and expectations of policy easing ahead.
          </p>
          <p>
            U.S. Treasury Bills (T-Bills) mature within one year; Treasury Notes
            (T-Notes) are medium-term; and Treasury Bonds (T-Bonds) are long-term.
            These instruments are regarded as low-risk benchmarks because they are
            backed by the U.S. government and are central to global rate pricing.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
