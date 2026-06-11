import calendar

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import fetch_btc_prices


_PERIOD_OPTIONS = ["Yearly", "Quarterly", "Monthly"]
_PERIOD_TO_PANDAS = {"Yearly": "Y", "Quarterly": "Q", "Monthly": "M"}
_TREND_WINDOWS = {"Yearly": 2, "Quarterly": 4, "Monthly": 12}
_SHEET_COLUMNS = {
    "Yearly": ["Year"],
    "Quarterly": ["Q1", "Q2", "Q3", "Q4"],
    "Monthly": [calendar.month_name[m] for m in range(1, 13)],
}


def _build_period_label(period_type: str, period: pd.Period) -> str:
    if period_type == "Yearly":
        return str(period.year)
    if period_type == "Quarterly":
        return f"{period.year} Q{period.quarter}"
    return period.strftime("%b %Y")


def _slot_info(period_type: str, period: pd.Period) -> tuple[int, str]:
    if period_type == "Yearly":
        return 1, "Year"
    if period_type == "Quarterly":
        quarter = int(period.quarter)
        return quarter, f"Q{quarter}"
    month = int(period.month)
    return month, calendar.month_name[month]


def _period_returns(prices_df: pd.DataFrame, period_type: str) -> pd.DataFrame:
    if prices_df.empty:
        return pd.DataFrame()

    frame = prices_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["date", "price"])
    frame = frame[frame["price"] > 0]
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    if frame.empty:
        return pd.DataFrame()

    period_code = _PERIOD_TO_PANDAS[period_type]
    frame["period"] = frame["date"].dt.to_period(period_code)

    rows = []
    for period, chunk in frame.groupby("period", sort=True):
        if chunk.empty:
            continue
        chunk = chunk.sort_values("date")
        open_price = float(chunk["price"].iloc[0])
        close_price = float(chunk["price"].iloc[-1])
        if not np.isfinite(open_price) or not np.isfinite(close_price) or open_price <= 0:
            continue

        period_return = (close_price / open_price) - 1.0
        if not np.isfinite(period_return):
            continue

        start_date = pd.Timestamp(chunk["date"].iloc[0]).normalize()
        end_date = pd.Timestamp(chunk["date"].iloc[-1]).normalize()
        slot_index, slot_label = _slot_info(period_type, period)

        rows.append(
            {
                "period_type": period_type,
                "period_start": start_date,
                "period_end": end_date,
                "period_label": _build_period_label(period_type, period),
                "slot_index": slot_index,
                "slot_label": slot_label,
                "year": int(start_date.year),
                "open_price": open_price,
                "close_price": close_price,
                "return": period_return,
                "return_pct": period_return * 100.0,
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("period_end").reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_historical_returns(_schema_version: int = 1) -> dict[str, pd.DataFrame]:
    btc_prices = fetch_btc_prices()
    if btc_prices.empty:
        return {}
    return {period: _period_returns(btc_prices, period) for period in _PERIOD_OPTIONS}


def _return_color(value: float) -> str:
    if value >= 0:
        return "rgba(52, 211, 153, 0.78)"
    return "rgba(248, 113, 113, 0.8)"


def _build_returns_spreadsheet_figure(period_df: pd.DataFrame, period_type: str) -> go.Figure:
    period_df = period_df.copy()
    if "return_pct" not in period_df.columns and "return" in period_df.columns:
        period_df["return_pct"] = pd.to_numeric(period_df["return"], errors="coerce") * 100.0
    if "year" not in period_df.columns:
        date_src = "period_start" if "period_start" in period_df.columns else "period_end"
        period_df["year"] = pd.to_datetime(period_df[date_src], errors="coerce").dt.year
    if "slot_label" not in period_df.columns:
        if period_type == "Yearly":
            period_df["slot_label"] = "Year"
        else:
            date_src = "period_end" if "period_end" in period_df.columns else "period_start"
            dt = pd.to_datetime(period_df[date_src], errors="coerce")
            if period_type == "Quarterly":
                period_df["slot_label"] = "Q" + dt.dt.quarter.astype("Int64").astype(str)
            else:
                period_df["slot_label"] = dt.dt.month.map(
                    lambda m: calendar.month_name[int(m)] if pd.notna(m) and int(m) > 0 else None
                )
    period_df = period_df.dropna(subset=["year", "slot_label", "return_pct"])

    sheet_cols = _SHEET_COLUMNS[period_type]
    pivot = period_df.pivot_table(
        index="year",
        columns="slot_label",
        values="return_pct",
        aggfunc="last",
    )
    pivot = pivot.reindex(columns=sheet_cols).sort_index(ascending=False)
    average_row = pivot.mean(axis=0, skipna=True)
    median_row = pivot.median(axis=0, skipna=True)
    stats_df = pd.DataFrame([average_row, median_row], index=["Average", "Median"])
    display_df = pd.concat([pivot, stats_df], axis=0)

    row_labels = [str(idx) for idx in display_df.index]
    time_col_colors = ["rgba(8, 11, 16, 0.95)"] * len(display_df)

    cell_values = [row_labels]
    cell_colors = [time_col_colors]

    year_rows = len(pivot)
    for col in sheet_cols:
        col_text = []
        col_fill = []
        values = display_df[col].tolist()
        for ridx, val in enumerate(values):
            is_stats_row = ridx >= year_rows
            if pd.isna(val):
                col_text.append("—")
                col_fill.append(
                    "rgba(107, 114, 128, 0.7)"
                    if is_stats_row
                    else "rgba(30, 41, 59, 0.45)"
                )
                continue

            col_text.append(f"{val:+.2f}%")
            if is_stats_row:
                col_fill.append("rgba(107, 114, 128, 0.82)")
            else:
                col_fill.append(
                    "rgba(52, 211, 153, 0.78)"
                    if val >= 0
                    else "rgba(248, 113, 113, 0.82)"
                )
        cell_values.append(col_text)
        cell_colors.append(col_fill)

    header_labels = ["Time"] + sheet_cols

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=header_labels,
                    fill_color="rgba(11, 15, 20, 0.98)",
                    align="center",
                    line_color="rgba(255, 255, 255, 0.08)",
                    font=dict(color="#e6e9ef", size=13),
                    height=42,
                ),
                cells=dict(
                    values=cell_values,
                    fill_color=cell_colors,
                    align="center",
                    line_color="rgba(15, 23, 42, 0.96)",
                    font=dict(color="#f8fafc", size=12),
                    height=36,
                ),
                columnwidth=[0.78] + [1.0] * len(sheet_cols),
            )
        ]
    )
    fig.update_layout(
        height=max(340, 160 + len(row_labels) * 36),
        margin=dict(l=6, r=6, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render(context: dict) -> None:
    favourites = context.get("favourites", set())
    toggle_favourite = context.get("toggle_favourite")

    # Schema version busts stale cached frames from earlier structure revisions.
    returns_map = _cached_historical_returns(_schema_version=2)
    if not returns_map:
        st.error("BTC price data is unavailable. Install yfinance or check your connection.")
        return

    default_period = st.session_state.get("btc_hist_returns_period", "Yearly")
    if default_period not in _PERIOD_OPTIONS:
        default_period = "Yearly"
    period_df = returns_map.get(default_period, pd.DataFrame())

    latest_text = "—"
    if not period_df.empty:
        latest_row = period_df.sort_values("period_end").iloc[-1]
        latest_text = f"{latest_row['return_pct']:+.2f}% ({latest_row['period_label']})"

    header_cols = st.columns([6, 1], gap="small")
    with header_cols[0]:
        st.markdown(
            f"""
            <div class="charts-header">
              <h3>Bitcoin Historical Returns</h3>
              <div class="charts-meta">Latest return: {latest_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        is_fav = "Bitcoin Historical Returns" in favourites
        fav_label = "Favourites" if is_fav else "Favourite"
        st.markdown(
            f'<div class="charts-filter-label">{fav_label}</div>',
            unsafe_allow_html=True,
        )
        if toggle_favourite:
            toggle_favourite("Bitcoin Historical Returns", "btc_historical_returns")

    with st.container(border=True):
        st.markdown('<div id="charts-filters"></div>', unsafe_allow_html=True)
        st.markdown('<div class="charts-filter-label">Return Interval</div>', unsafe_allow_html=True)
        period_choice = st.selectbox(
            "Return Interval",
            options=_PERIOD_OPTIONS,
            index=_PERIOD_OPTIONS.index(default_period),
            key="btc_hist_returns_period",
            label_visibility="collapsed",
        )

    chart_df = returns_map.get(period_choice, pd.DataFrame())
    if chart_df.empty:
        st.info("No data available for the selected filters.")
        return

    fig = go.Figure()
    colors = [_return_color(v) for v in chart_df["return_pct"]]
    fig.add_trace(
        go.Bar(
            x=chart_df["period_end"],
            y=chart_df["return_pct"],
            name="Period Return",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.12)", width=0.5)),
            customdata=np.column_stack(
                [
                    chart_df["period_label"].astype(str).to_numpy(),
                    chart_df["period_start"].dt.strftime("%Y-%m-%d").to_numpy(),
                    chart_df["period_end"].dt.strftime("%Y-%m-%d").to_numpy(),
                    chart_df["open_price"].to_numpy(),
                    chart_df["close_price"].to_numpy(),
                ]
            ),
            hovertemplate=(
                "%{customdata[0]}<br>"
                "Return: %{y:+.2f}%<br>"
                "Start: %{customdata[1]} ($%{customdata[3]:,.2f})<br>"
                "End: %{customdata[2]} ($%{customdata[4]:,.2f})<extra></extra>"
            ),
        )
    )

    trend_window = _TREND_WINDOWS[period_choice]
    trend = chart_df["return_pct"].rolling(window=trend_window, min_periods=2).mean()
    fig.add_trace(
        go.Scatter(
            x=chart_df["period_end"],
            y=trend,
            mode="lines",
            name=f"{trend_window}-period average",
            line=dict(color="#60a5fa", width=2.2),
            hovertemplate=f"{trend_window}-period avg: %{{y:+.2f}}%<extra></extra>",
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
        bargap=0.16,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="left",
            x=0.0,
            font=dict(color="#e6e9ef"),
        ),
        hoverlabel=dict(
            bgcolor="#0b0f14",
            bordercolor="rgba(96, 165, 250, 0.4)",
            font=dict(color="#e6e9ef"),
        ),
        uirevision=f"btc-historical-returns-{period_choice}",
    )
    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.28)")
    fig.update_xaxes(
        title_text="Date",
        showgrid=False,
        zeroline=False,
        tickformat="%Y",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikecolor="rgba(255,255,255,0.45)",
        spikethickness=0.4,
    )
    fig.update_yaxes(
        title_text="Return (%)",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
    )

    with st.container(border=True):
        st.plotly_chart(
            fig,
            use_container_width=True,
            key="btc_historical_returns_plot",
            config={
                "displayModeBar": False,
                "scrollZoom": False,
                "doubleClick": "reset",
                "showTips": False,
                "responsive": True,
            },
        )

    sheet_fig = _build_returns_spreadsheet_figure(chart_df, period_choice)
    with st.container(border=True):
        st.plotly_chart(
            sheet_fig,
            use_container_width=True,
            key="btc_historical_returns_spreadsheet",
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
            This chart shows Bitcoin period returns across its full available history.
            Returns are computed as close-to-open change for each selected period
            (yearly, quarterly, or monthly).
          </p>
          <p>
            The spreadsheet view below the chart uses the exact same interval filter and
            shows the distribution of returns by calendar slot (month, quarter, or year),
            including Average and Median summary rows.
          </p>
          <h4>Usage</h4>
          <p>
            Use the interval filter to switch time granularity for both views at once.
            The bar chart highlights period-by-period dispersion, while the spreadsheet
            provides a fast regime comparison across Bitcoin history.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
