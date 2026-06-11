from datetime import date
import html

import pandas as pd
import plotly.express as px
import streamlit as st

from tracker.services import daily_pnl_calendar, month_range, month_weeks


def _inject_calendar_styles():
    st.markdown(
        """
        <style>
        .pnl-cal {display:grid;grid-template-columns:repeat(7,1fr);gap:12px;margin-top:6px;}
        .pnl-head {display:grid;grid-template-columns:repeat(7,1fr);gap:12px;margin-top:6px;}
        .pnl-head div {color:var(--muted);font-size:0.9rem;text-align:center;}
        .pnl-cell {background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:10px 8px;min-height:68px;}
        .pnl-day {font-weight:700;color:var(--text);font-size:1rem;}
        .pnl-val {margin-top:6px;font-weight:600;}
        .pnl-pos {background:rgba(34, 197, 94, 0.12);border-color:rgba(34, 197, 94, 0.25);}
        .pnl-neg {background:rgba(239, 68, 68, 0.12);border-color:rgba(239, 68, 68, 0.25);}
        .pnl-zero {background:var(--surface);}
        .pnl-pos .pnl-val {color:var(--positive);}
        .pnl-neg .pnl-val {color:var(--negative);}
        .pnl-zero .pnl-val {color:var(--muted);}
        .pnl-cell {position:relative;}
        .pnl-cell[data-tooltip] {cursor:default;}
        .pnl-cell[data-tooltip]::after {
          content: attr(data-tooltip);
          position:absolute;
          left:50%;
          bottom:110%;
          transform:translateX(-50%);
          background:var(--surface-2);
          color:var(--text);
          border:1px solid var(--border);
          padding:10px 12px;
          border-radius:10px;
          box-shadow:0 8px 24px rgba(0,0,0,0.4);
          white-space:pre-line;
          opacity:0;
          pointer-events:none;
          transition:opacity 120ms ease-in-out;
          min-width:180px;
          z-index:10;
        }
        .pnl-cell[data-tooltip]:hover::after {opacity:1;}
        .pnl-month-pill {display:inline-block;padding:6px 14px;border-radius:999px;
            background:var(--surface-2);border:1px solid var(--border);
            color:var(--text);font-weight:600;}
        .pnl-stat {background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:10px;}
        .pnl-stat h4 {margin:0 0 6px 0;color:var(--text);font-size:1rem;}
        .pnl-stat .num {font-size:1.05rem;font-weight:700;}
        .pnl-stat .pos {color:var(--positive);}
        .pnl-stat .neg {color:var(--negative);}
        .pnl-stat .muted {color:var(--muted);}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_calendar(trades_df, selected_accounts, accounts_map, trades_all):
    st.subheader("Daily PnL")
    if trades_df.empty:
        st.info("No trades to show.")
        return
    active_account = selected_accounts[0] if selected_accounts else None
    if active_account:
        trades_df = trades_df[trades_df["account"] == active_account]
        trades_all = trades_all[trades_all["account"] == active_account]

    _, min_dt, max_dt = month_range(trades_df)
    min_month = date(min_dt.year, min_dt.month, 1)
    max_month = date(max_dt.year, max_dt.month, 1)

    if "pnl_month" not in st.session_state:
        st.session_state.pnl_month = max_month

    month_pick = st.session_state.pnl_month
    daily = daily_pnl_calendar(trades_df, month_pick)
    daily_map = {row["day"]: row["pnl"] for _, row in daily.iterrows()}
    day_trades = {}
    if not trades_df.empty:
        for _, row in trades_df.iterrows():
            day_key = row["trade_time"].date()
            day_trades.setdefault(day_key, []).append(row)

    weeks = month_weeks(month_pick)
    _inject_calendar_styles()

    cal_col, stat_col = st.columns([4, 2], gap="large")
    with cal_col:
        nav_left, nav_mid, nav_right = st.columns([1, 4, 1])
        with nav_left:
            if st.button("◀", use_container_width=True) and st.session_state.pnl_month > min_month:
                prev = st.session_state.pnl_month.replace(day=1) - pd.offsets.MonthBegin(1)
                st.session_state.pnl_month = prev.date()
                st.rerun()
        with nav_mid:
            st.markdown(
                f'<div style="text-align:center;"><span class="pnl-month-pill">Month • {st.session_state.pnl_month.strftime("%Y-%m")}</span></div>',
                unsafe_allow_html=True,
            )
        with nav_right:
            if st.button("▶", use_container_width=True) and st.session_state.pnl_month < max_month:
                nxt = st.session_state.pnl_month.replace(day=1) + pd.offsets.MonthBegin(1)
                st.session_state.pnl_month = nxt.date()
                st.rerun()
        st.markdown("<div style='height:0px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="pnl-head">
              <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cells = []
        for week in weeks:
            for day_num in week:
                if day_num == 0:
                    cells.append('<div class="pnl-cell pnl-zero"></div>')
                    continue
                day_date = date(month_pick.year, month_pick.month, day_num)
                pnl_val = float(daily_map.get(day_date, 0.0))
                cls = "pnl-zero"
                if pnl_val > 0:
                    cls = "pnl-pos"
                elif pnl_val < 0:
                    cls = "pnl-neg"
                pnl_text = f"{pnl_val:+.2f}" if pnl_val != 0 else "0.00"
                tooltip = ""
                trades = day_trades.get(day_date, [])
                if trades:
                    lines = []
                    for trade in trades:
                        action = trade.get("action", "Trade")
                        symbol = trade.get("symbol", "")
                        ttype = trade.get("type", "")
                        pnl = float(trade.get("pnl", 0.0))
                        line = f"{action} {symbol} {ttype}".strip()
                        line = f"{line}  |  PnL: {pnl:+.2f}"
                        lines.append(line)
                    tooltip = html.escape("\n".join(lines), quote=True)
                    cells.append(
                        f'<div class="pnl-cell {cls}" data-tooltip="{tooltip}">'
                        f'<div class="pnl-day">{day_num}</div>'
                        f'<div class="pnl-val">{pnl_text}</div></div>'
                    )
                else:
                    cells.append(
                        f'<div class="pnl-cell {cls}"><div class="pnl-day">{day_num}</div>'
                        f'<div class="pnl-val">{pnl_text}</div></div>'
                    )
        st.markdown(f'<div class="pnl-cal">{"".join(cells)}</div>', unsafe_allow_html=True)

    with stat_col:
        st.markdown("<div style='height:0px;'></div>", unsafe_allow_html=True)
        month_total = float(daily["pnl"].sum()) if not daily.empty else 0.0
        green_days = int((daily["pnl"] > 0).sum()) if not daily.empty else 0
        red_days = int((daily["pnl"] < 0).sum()) if not daily.empty else 0
        flat_days = int((daily["pnl"] == 0).sum()) if not daily.empty else 0
        stat_class = "pos" if month_total > 0 else "neg" if month_total < 0 else "muted"
        account_total = 0.0
        if active_account:
            acc_start = accounts_map.get(active_account, 0.0)
            acc_pnl = trades_all["pnl"].sum() if not trades_all.empty else 0.0
            account_total = acc_start + acc_pnl
        balance_class = "pos" if account_total > 0 else "muted"
        st.markdown(
            f"""
            <div class="pnl-stat">
              <h4>Current Balance</h4>
              <div class="num {balance_class}">${account_total:,.2f}</div>
              <div class="muted">Total across selected accounts</div>
            </div>
            <div style="height:6px;"></div>
            <div class="pnl-stat">
              <h4>Month Summary</h4>
              <div class="num {stat_class}">${month_total:,.2f}</div>
              <div class="muted">Total PnL</div>
              <hr style="border:0;border-top:1px solid rgba(255,255,255,0.08);margin:10px 0;">
              <div class="muted">Green days: {green_days}</div>
              <div class="muted">Red days: {red_days}</div>
              <div class="muted">Flat days: {flat_days}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    month_trades = trades_df.copy()
    month_trades = month_trades[
        (month_trades["trade_time"].dt.year == month_pick.year)
        & (month_trades["trade_time"].dt.month == month_pick.month)
    ]
    if "action" in month_trades.columns:
        month_trades = month_trades[month_trades["action"] == "Trade"]

    wins = int((month_trades["pnl"] > 0).sum()) if not month_trades.empty else 0
    losses = int((month_trades["pnl"] < 0).sum()) if not month_trades.empty else 0
    pie_df = pd.DataFrame(
        {
            "result": ["Win", "Loss"],
            "count": [wins, losses],
        }
    )
    pie_fig = px.pie(
        pie_df,
        values="count",
        names="result",
        hole=0.55,
    )
    pie_fig.update_traces(
        marker=dict(colors=["#22c55e", "#ef4444"]),
        textinfo="percent+label",
        hoverinfo="skip",
    )
    pie_fig.update_layout(
        height=200,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6e9ef"),
        showlegend=False,
        transition_duration=600,
    )
    with cal_col:
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        if not trades_all.empty:
            month_series = trades_all.copy()
            if "action" in month_series.columns:
                month_series = month_series[month_series["action"] == "Trade"]
            month_series["month"] = month_series["trade_time"].dt.to_period("M").dt.to_timestamp()
            month_pnl = (
                month_series.groupby("month", as_index=False)["pnl"].sum().sort_values("month")
            )
            month_pnl["color"] = month_pnl["pnl"].apply(
                lambda v: "#22c55e" if v >= 0 else "#ef4444"
            )
            bar_fig = px.bar(month_pnl, x="month", y="pnl")
            bar_fig.update_traces(marker_color=month_pnl["color"])
            bar_fig.update_layout(
                height=220,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e6e9ef"),
                showlegend=False,
            )
            bar_fig.update_xaxes(tickformat="%Y-%m")
            bar_fig.update_yaxes(zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
            with st.container(border=True):
                st.markdown("**Monthly PnL (All Time)**")
                st.plotly_chart(bar_fig, use_container_width=True, config={"displayModeBar": False})

    with stat_col:
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        avg_trade = float(month_trades["pnl"].mean()) if not month_trades.empty else 0.0
        avg_win = (
            float(month_trades.loc[month_trades["pnl"] > 0, "pnl"].mean())
            if not month_trades.empty
            else 0.0
        )
        avg_loss = (
            float(month_trades.loc[month_trades["pnl"] < 0, "pnl"].mean())
            if not month_trades.empty
            else 0.0
        )
        avg_class = "pos" if avg_trade > 0 else "neg" if avg_trade < 0 else "muted"
        avg_win_class = "pos" if avg_win > 0 else "muted"
        avg_loss_class = "neg" if avg_loss < 0 else "muted"
        st.markdown(
            f"""
            <div class="pnl-stat">
              <h4>Average Trade</h4>
              <div class="num {avg_class}">${avg_trade:,.2f}</div>
              <div class="muted">Mean PnL per trade</div>
              <hr style="border:0;border-top:1px solid rgba(255,255,255,0.08);margin:10px 0;">
              <div class="muted">Avg Win: <span class="{avg_win_class}">${avg_win:,.2f}</span></div>
              <div class="muted">Avg Loss: <span class="{avg_loss_class}">${avg_loss:,.2f}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**Win / Loss Ratio**")
            st.plotly_chart(pie_fig, use_container_width=True, config={"displayModeBar": False})
