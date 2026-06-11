import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import FRED_SERIES, fetch_fred_series


@st.cache_data(show_spinner=False, ttl=3600)
def _load_curve_data(selected, start_key, smoothing_choice, api_key):
    frames = []
    start_date = pd.to_datetime(start_key) if start_key else None
    for label in selected:
        series_id = FRED_SERIES[label]
        df = fetch_fred_series(series_id, api_key)
        if df.empty:
            continue
        if start_date is not None:
            df = df[df["date"] >= start_date]
        df["series"] = label
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    curve_df = pd.concat(frames, ignore_index=True)
    curve_df = curve_df.sort_values("date")

    if smoothing_choice != "None":
        window = 7 if "7D" in smoothing_choice else 30
        curve_df["value"] = (
            curve_df.groupby("series")["value"]
            .transform(lambda s: s.rolling(window=window, min_periods=1).mean())
        )
    return curve_df


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
        toolbar_cols = st.columns([1, 1, 1], gap="small")
        with toolbar_cols[0]:
            st.markdown('<div class="charts-filter-label">Range</div>', unsafe_allow_html=True)
            range_choice = st.selectbox(
                "Range",
                options=["1Y", "3Y", "5Y", "10Y", "Max"],
                index=1,
                label_visibility="collapsed",
            )
        with toolbar_cols[1]:
            st.markdown('<div class="charts-filter-label">Smoothing</div>', unsafe_allow_html=True)
            smoothing_choice = st.selectbox(
                "Smoothing",
                options=["None", "7D SMA", "30D SMA"],
                index=0,
                label_visibility="collapsed",
            )
        with toolbar_cols[2]:
            st.markdown('<div class="charts-filter-label">Scale</div>', unsafe_allow_html=True)
            scale_choice = st.selectbox(
                "Scale",
                options=["Linear", "Log"],
                index=0,
                label_visibility="collapsed",
            )

    curve_options = list(FRED_SERIES.keys())
    selected = ["1Y", "2Y", "5Y", "10Y", "30Y"]
    with st.expander("Series", expanded=False):
        selected = st.multiselect(
            "Select maturities",
            options=curve_options,
            default=selected,
        )

    if not selected:
        st.info("Select at least one maturity to display the curve.")
        return

    today = pd.Timestamp.today().normalize()
    if range_choice == "Max":
        start_date = None
    else:
        years = int(range_choice.replace("Y", ""))
        start_date = today - pd.DateOffset(years=years)

    selected_key = tuple(selected)
    start_key = start_date.strftime("%Y-%m-%d") if start_date is not None else ""
    curve_df = _load_curve_data(selected_key, start_key, smoothing_choice, api_key)
    if curve_df.empty:
        st.warning("No data returned for the selected range.")
        return

    color_map = {
        "1M": "#94a3b8",
        "3M": "#38bdf8",
        "6M": "#22c55e",
        "1Y": "#f59e0b",
        "2Y": "#e879f9",
        "5Y": "#6366f1",
        "10Y": "#f97316",
        "30Y": "#14b8a6",
    }

    fig = go.Figure()
    for label in selected:
        series_df = curve_df[curve_df["series"] == label]
        if series_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series_df["date"],
                y=series_df["value"],
                mode="lines",
                name=label,
                line=dict(
                    width=2.6,
                    color=color_map.get(label, "#38bdf8"),
                    shape="spline",
                    smoothing=1.1,
                ),
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "%{x|%b %d, %Y}<br>"
                    "Yield: %{y:.2f}%<extra></extra>"
                ),
            )
        )

    latest_date = curve_df["date"].max()
    last_stamp = latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else "—"
    with header_container:
        header_cols = st.columns([6, 1], gap="small")
        with header_cols[0]:
            st.markdown(
                f"""
                <div class="charts-header">
                  <h3>U.S. Treasury Yield Curve</h3>
                  <div class="charts-meta">Updated: {last_stamp} • {len(selected)} series • Source: FRED</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            is_fav = "Treasury Yield Curve" in favourites
            fav_label = "Favourites" if is_fav else "Favourite"
            st.markdown(
                f'<div class="charts-filter-label">{fav_label}</div>',
                unsafe_allow_html=True,
            )
            if toggle_favourite:
                toggle_favourite("Treasury Yield Curve", "treasury_curve")

    fig.update_layout(
        height=700,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=30, r=20, t=10, b=50),
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
            bordercolor="rgba(56, 189, 248, 0.4)",
            font=dict(color="#e6e9ef"),
        ),
        uirevision="treasury-yield-curve",
    )
    fig.update_yaxes(
        title_text="Yield (%)",
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        title_font=dict(size=14),
        tickfont=dict(size=12),
    )
    fig.update_xaxes(
        title_text="Date",
        showgrid=False,
        zeroline=False,
        tickformat="%Y",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(56, 189, 248, 0.35)",
        spikethickness=1,
        title_font=dict(size=14),
        tickfont=dict(size=12),
    )

    use_log = scale_choice == "Log" and (curve_df["value"] > 0).all()
    if scale_choice == "Log" and not use_log:
        st.caption("Log scale is unavailable because some yields are zero or negative.")
    if use_log:
        fig.update_yaxes(type="log")

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
            The Treasury yield curve plots the yields on U.S. government securities
            across maturities, capturing the market’s consensus on growth, inflation,
            and policy expectations. A steeper curve typically signals improving
            growth prospects and rising term premiums, while a flatter or inverted
            curve reflects tighter financial conditions and expectations of lower
            policy rates ahead.
          </p>
          <p>
            Yield curves influence borrowing costs throughout the economy. Mortgages,
            corporate credit, and valuation models often reference Treasury yields,
            so shifts in the curve can affect equity risk premiums, credit spreads,
            and capital allocation decisions across markets.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
