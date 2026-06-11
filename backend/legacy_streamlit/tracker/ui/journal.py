"""
journal.py — Trade Journal
Design: matches dashboard — IBM Plex Sans/Mono, TradingView × Binance Pro aesthetic.
Changes vs original:
  - Calendar / daily PnL section removed
  - Sorting, filtering, and search controls added to the trade table
  - Full redesign to match dashboard CSS
"""
from datetime import datetime, time as dtime

import pandas as pd
import streamlit as st
from bson import ObjectId

from tracker.services import get_accounts, load_trades

# ─── Design tokens (must match dashboard.py) ──────────────────────────────────
T = {
    "bg":       "#0b0e17",
    "surface":  "#131722",
    "elevated": "#1a2035",
    "border":   "#232b3e",
    "border2":  "#2d3a52",
    "text":     "#eaecef",
    "text2":    "#848e9c",
    "text3":    "#4a5568",
    "pos":      "#0ecb81",
    "neg":      "#f6465d",
    "gold":     "#f0b90b",
    "blue":     "#1677ff",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: 'IBM Plex Sans', sans-serif;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: #0b0e17 !important; }
.block-container {
  padding: 0 2.25rem 5rem 2.25rem !important;
  max-width: 1480px !important;
}
header[data-testid="stHeader"],
footer, #MainMenu, .stDeployButton { display: none !important; }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0b0e17; }
::-webkit-scrollbar-thumb { background: #232b3e; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2d3a52; }

/* ── nav bar ────────────────────────────────────────────────────────────────── */
.nav-wrap {
  display: flex;
  align-items: center;
  height: 56px;
  border-bottom: 1px solid #232b3e;
  margin-bottom: 0;
  gap: 1.5rem;
}
.nav-brand {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.95rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: 0.02em;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}
.nav-dot {
  width: 6px; height: 6px;
  background: #0ecb81;
  border-radius: 50%;
  display: inline-block;
}

/* ── page heading ───────────────────────────────────────────────────────────── */
.page-title {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.1rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.01em;
  margin-bottom: 0.25rem;
}
.page-sub {
  font-size: 0.75rem;
  color: #4a5568;
  margin-bottom: 1.4rem;
}

/* ── section label ──────────────────────────────────────────────────────────── */
.section-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #848e9c;
  margin-bottom: 0.9rem;
}

/* ── card ───────────────────────────────────────────────────────────────────── */
.card {
  background: #131722;
  border: 1px solid #232b3e;
  border-radius: 8px;
  padding: 1.25rem 1.4rem;
  margin-bottom: 1rem;
}
.card:hover {
  border-color: #2d3a52;
  transition: border-color 0.15s ease;
}

/* ── stats strip ────────────────────────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: #232b3e;
  border: 1px solid #232b3e;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1rem;
}
.stat-cell {
  background: #131722;
  padding: 1rem 1.25rem;
}
.stat-cell:hover { background: #161d2e; }
.stat-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.62rem;
  font-weight: 400;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #848e9c;
  margin-bottom: 0.4rem;
}
.stat-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.2rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.01em;
  line-height: 1.1;
}
.stat-num.pos { color: #0ecb81; }
.stat-num.neg { color: #f6465d; }
.stat-sub {
  font-size: 0.68rem;
  color: #4a5568;
  margin-top: 0.3rem;
}

/* ── filter bar ─────────────────────────────────────────────────────────────── */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

/* ── trade row badge ────────────────────────────────────────────────────────── */
.badge {
  display: inline-block;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.6rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 3px;
  vertical-align: middle;
}

/* ── form labels & inputs ───────────────────────────────────────────────────── */
div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stDateInput"] label {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.65rem !important;
  font-weight: 400 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: #848e9c !important;
  margin-bottom: 4px !important;
}
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {
  background: #1a2035 !important;
  border: 1px solid #232b3e !important;
  border-radius: 6px !important;
  color: #eaecef !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.82rem !important;
}
div[data-testid="stSelectbox"] > div > div:focus-within,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stTextInput"] input:focus {
  border-color: #2d3a52 !important;
  outline: none !important;
  box-shadow: none !important;
}
div[data-testid="stDateInput"] input {
  background: #1a2035 !important;
  border: 1px solid #232b3e !important;
  border-radius: 6px !important;
  color: #eaecef !important;
  font-family: 'IBM Plex Mono', monospace !important;
}

/* ── buttons ────────────────────────────────────────────────────────────────── */
.stButton > button {
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.02em !important;
  background: #1a2035 !important;
  border: 1px solid #232b3e !important;
  color: #eaecef !important;
  border-radius: 6px !important;
  padding: 0.45rem 1rem !important;
  height: auto !important;
  transition: all 0.12s ease !important;
}
.stButton > button:hover {
  background: #232b3e !important;
  border-color: #2d3a52 !important;
  color: #eaecef !important;
}
.stButton > button[kind="primary"] {
  background: #0ecb81 !important;
  border-color: #0ecb81 !important;
  color: #0b0e17 !important;
  font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
  background: #0bb872 !important;
  border-color: #0bb872 !important;
  color: #0b0e17 !important;
}
.stButton > button[kind="secondary"] {
  color: #f6465d !important;
  border-color: rgba(246,70,93,0.35) !important;
}
.stButton > button[kind="secondary"]:hover {
  background: rgba(246,70,93,0.08) !important;
  border-color: #f6465d !important;
}

/* ── expander ───────────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
  background: #131722 !important;
  border: 1px solid #232b3e !important;
  border-radius: 8px !important;
  overflow: hidden;
}
div[data-testid="stExpander"] summary {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.06em !important;
  color: #848e9c !important;
  padding: 0.7rem 1rem !important;
}
div[data-testid="stExpander"] summary:hover { color: #eaecef !important; }
div[data-testid="stExpander"] > div > div { padding: 0 1rem 1rem 1rem !important; }

/* ── dataframe ──────────────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] > div {
  border-radius: 6px !important;
  border: 1px solid #232b3e !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.78rem !important;
}

/* ── alerts ─────────────────────────────────────────────────────────────────── */
div[data-testid="stAlert"] {
  border-radius: 6px !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.75rem !important;
  border-left-width: 3px !important;
}
div[data-testid="stSuccessAlert"] {
  background: rgba(14,203,129,0.07) !important;
  border-left-color: #0ecb81 !important;
  color: #0ecb81 !important;
}
div[data-testid="stWarningAlert"] {
  background: rgba(240,185,11,0.07) !important;
  border-left-color: #f0b90b !important;
  color: #f0b90b !important;
}

/* ── divider ────────────────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid #232b3e !important; margin: 1rem 0 !important; }

/* ── multiselect ────────────────────────────────────────────────────────────── */
div[data-testid="stMultiSelect"] label {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.65rem !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: #848e9c !important;
}
div[data-testid="stMultiSelect"] > div > div {
  background: #1a2035 !important;
  border: 1px solid #232b3e !important;
  border-radius: 6px !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.78rem !important;
}
</style>
"""


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _money(v: float, sign: bool = False) -> str:
    prefix = ("+" if v >= 0 else "") if sign else ""
    return f"{prefix}${v:,.2f}"


def _pct(v: float) -> str:
    s = "+" if v >= 0 else ""
    return f"{s}{v:.2f}%"


def _journal_stats(df: pd.DataFrame) -> dict:
    trades = df[df["action"] == "Trade"] if not df.empty else pd.DataFrame()
    n = len(trades)
    n_wins = int((trades["pnl"] > 0).sum()) if not trades.empty else 0
    n_loss = int((trades["pnl"] < 0).sum()) if not trades.empty else 0
    total  = float(df["pnl"].sum()) if not df.empty else 0.0
    avg    = float(trades["pnl"].mean()) if not trades.empty else 0.0
    win_r  = n_wins / n * 100 if n > 0 else 0.0
    return {
        "n": n, "n_wins": n_wins, "n_loss": n_loss,
        "total": total, "avg": avg, "win_rate": win_r,
    }


def _stats_html(s: dict) -> str:
    tc = "pos" if s["total"] >= 0 else "neg"
    ac = "pos" if s["avg"]   >= 0 else "neg"
    wc = "pos" if s["win_rate"] >= 50 else "neg"
    return f"""
<div class="stats-row">
  <div class="stat-cell">
    <div class="stat-lbl">Total Trades</div>
    <div class="stat-num">{s['n']}</div>
    <div class="stat-sub">{s['n_wins']} winning · {s['n_loss']} losing</div>
  </div>
  <div class="stat-cell">
    <div class="stat-lbl">Win Rate</div>
    <div class="stat-num {wc}">{s['win_rate']:.1f}%</div>
    <div class="stat-sub">{s['n_wins']} of {s['n']} trades</div>
  </div>
  <div class="stat-cell">
    <div class="stat-lbl">Total Realised P&amp;L</div>
    <div class="stat-num {tc}">{_money(s['total'], sign=True)}</div>
    <div class="stat-sub">Across all filtered trades</div>
  </div>
  <div class="stat-cell">
    <div class="stat-lbl">Average Trade P&amp;L</div>
    <div class="stat-num {ac}">{_money(s['avg'], sign=True)}</div>
    <div class="stat-sub">Mean per closed trade</div>
  </div>
  <div class="stat-cell">
    <div class="stat-lbl">Net Deposits / Withdrawals</div>
    <div class="stat-num">{_money(float(s['total']))}</div>
    <div class="stat-sub">Realised P&amp;L included</div>
  </div>
</div>"""


def render_journal(db):
    st.markdown(_CSS, unsafe_allow_html=True)

    active_user = st.session_state.get("auth_user")
    if not active_user:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;'
            f'height:60vh;font-family:IBM Plex Mono,monospace;font-size:0.85rem;'
            f'color:{T["text2"]};">Please log in to access your journal.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Account data ──
    existing_accounts = get_accounts(db, active_user)
    existing_names    = [a["name"] for a in existing_accounts]
    accounts_map      = {a["name"]: a.get("starting_balance", 0.0) for a in existing_accounts}

    # ══════════════════════════════════════════════════════════════════════════
    #  NAV BAR
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
    col_brand, col_sel = st.columns([1, 3], gap="medium")

    with col_brand:
        st.markdown(
            '<div class="nav-brand" style="padding-top:1.35rem;">'
            '<span class="nav-dot"></span>Portfolio Tracker'
            '</div>',
            unsafe_allow_html=True,
        )

    with col_sel:
        st.markdown('<div style="padding-top:1.05rem;"></div>', unsafe_allow_html=True)
        selected_account = st.selectbox(
            "account_selector",
            options=existing_names,
            index=0 if existing_names else None,
            label_visibility="collapsed",
            placeholder="Select account…",
            key="journal_acct",
        )

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1.5rem;"></div>', unsafe_allow_html=True)

    # ── Page heading ──
    st.markdown(
        '<div class="page-title">Trade Journal</div>'
        '<div class="page-sub">Review, filter, and manage your trade history.</div>',
        unsafe_allow_html=True,
    )

    if not selected_account:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;height:40vh;'
            f'font-family:IBM Plex Mono,monospace;font-size:0.82rem;color:{T["text2"]};">'
            'Select an account to view its journal.</div>',
            unsafe_allow_html=True,
        )
        return

    selected_accounts = [selected_account]
    trades_df = load_trades(db, selected_accounts, active_user)

    # ══════════════════════════════════════════════════════════════════════════
    #  STATS STRIP  (computed on full, unfiltered dataset first)
    # ══════════════════════════════════════════════════════════════════════════
    raw_stats = _journal_stats(trades_df)
    st.markdown(_stats_html(raw_stats), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  TRADE TABLE  —  filters + sorting
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Trade History</div>', unsafe_allow_html=True)

    if trades_df.empty:
        st.info("No trades recorded for this account.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        display = trades_df.copy()
        display["trade_time"] = pd.to_datetime(display["trade_time"], utc=True, errors="coerce")

        # ── Filter controls ──
        f1, f2, f3, f4, f5 = st.columns([1.6, 1.2, 1.2, 1.2, 1.4], gap="small")

        with f1:
            search = st.text_input("Search symbol", placeholder="e.g. BTCUSDT", key="jf_search")

        with f2:
            action_opts = ["All"] + sorted(display["action"].dropna().unique().tolist())
            action_filter = st.selectbox("Action", options=action_opts, key="jf_action")

        with f3:
            # Direction filter (Long / Short) — only relevant for trades
            dir_opts = ["All"]
            if "type" in display.columns:
                types = display["type"].dropna().unique().tolist()
                dir_opts += sorted([t for t in types if t])
            direction_filter = st.selectbox("Direction", options=dir_opts, key="jf_dir")

        with f4:
            pnl_opts = ["All", "Profitable (+)", "Losing (−)", "Break-even"]
            pnl_filter = st.selectbox("Result", options=pnl_opts, key="jf_pnl")

        with f5:
            sort_opts = [
                "Date — Newest First",
                "Date — Oldest First",
                "P&L — Highest First",
                "P&L — Lowest First",
                "Symbol A→Z",
                "Symbol Z→A",
            ]
            sort_by = st.selectbox("Sort By", options=sort_opts, key="jf_sort")

        # ── Apply filters ──
        filtered = display.copy()

        if search.strip():
            filtered = filtered[
                filtered["symbol"].str.upper().str.contains(search.strip().upper(), na=False)
            ]

        if action_filter != "All":
            filtered = filtered[filtered["action"] == action_filter]

        if direction_filter != "All":
            filtered = filtered[filtered.get("type", pd.Series(dtype=str)) == direction_filter]

        if pnl_filter == "Profitable (+)":
            filtered = filtered[filtered["pnl"] > 0]
        elif pnl_filter == "Losing (−)":
            filtered = filtered[filtered["pnl"] < 0]
        elif pnl_filter == "Break-even":
            filtered = filtered[filtered["pnl"] == 0]

        # ── Apply sort ──
        sort_map = {
            "Date — Newest First":  ("trade_time", False),
            "Date — Oldest First":  ("trade_time", True),
            "P&L — Highest First":  ("pnl",        False),
            "P&L — Lowest First":   ("pnl",        True),
            "Symbol A→Z":           ("symbol",     True),
            "Symbol Z→A":           ("symbol",     False),
        }
        sort_col, sort_asc = sort_map[sort_by]
        filtered = filtered.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)

        # ── Result count ──
        count_color = T["text2"] if len(filtered) > 0 else T["neg"]
        st.markdown(
            f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.7rem;'
            f'color:{count_color};margin-bottom:0.6rem;">'
            f'{len(filtered)} result{"s" if len(filtered) != 1 else ""} '
            f'{"(filtered)" if len(filtered) != len(display) else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Build display dataframe ──
        show_cols = ["trade_time", "action", "type", "symbol", "pnl"]
        safe_cols = [c for c in show_cols if c in filtered.columns]
        view = filtered[safe_cols].copy()

        # Format columns
        view["trade_time"] = view["trade_time"].dt.strftime("%Y-%m-%d")
        view["pnl"] = view["pnl"].apply(lambda v: f"+${v:,.2f}" if v > 0 else f"-${abs(v):,.2f}" if v < 0 else "$0.00")
        view = view.rename(columns={
            "trade_time": "Date",
            "action":     "Action",
            "type":       "Direction",
            "symbol":     "Symbol",
            "pnl":        "P&L",
        })

        if filtered.empty:
            st.info("No trades match the current filters.")
        else:
            # Filtered stats
            filt_stats = _journal_stats(filtered)
            filt_pnl = filt_stats["total"]
            fpnl_col = T["pos"] if filt_pnl >= 0 else T["neg"]
            st.markdown(
                f'<div style="display:flex;gap:1.5rem;font-family:IBM Plex Mono,monospace;'
                f'font-size:0.72rem;color:{T["text3"]};margin-bottom:0.5rem;">'
                f'<span>Filtered P&amp;L: <span style="color:{fpnl_col};font-weight:600;">{_money(filt_pnl, sign=True)}</span></span>'
                f'<span>Win Rate: <span style="color:{T["text2"]};">{filt_stats["win_rate"]:.1f}%</span></span>'
                f'<span>Avg: <span style="color:{T["text2"]};">{_money(filt_stats["avg"], sign=True)}</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(view, use_container_width=True, hide_index=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  EDIT / DELETE TRADE
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div style="height:0.25rem;"></div>', unsafe_allow_html=True)

    with st.expander("✎  Edit or Delete a Trade"):
        st.markdown(
            f'<div style="font-size:0.72rem;color:{T["text3"]};margin-bottom:0.85rem;">'
            'Select any trade to modify its details or remove it from your journal.</div>',
            unsafe_allow_html=True,
        )

        edit_df = load_trades(db, selected_accounts, active_user)
        if edit_df.empty:
            st.info("No trades available to edit.")
        else:
            edit_df = edit_df.copy()
            edit_df["id_str"] = edit_df["_id"].astype(str)
            edit_df["trade_time"] = pd.to_datetime(edit_df["trade_time"], utc=True, errors="coerce")
            edit_df["label"] = edit_df.apply(
                lambda row: (
                    f"{row['trade_time'].strftime('%Y-%m-%d')}  ·  "
                    f"{row.get('action','Trade')}  ·  "
                    f"{row['symbol']}  ·  "
                    f"{'%+.2f' % row['pnl']}"
                ),
                axis=1,
            )

            choice = st.selectbox("Select trade to edit", options=edit_df["label"].tolist(), key="edit_choice")
            selected_row = edit_df.loc[edit_df["label"] == choice].iloc[0]

            st.markdown('<hr style="margin:0.75rem 0;">', unsafe_allow_html=True)

            col_a, col_b = st.columns(2, gap="medium")
            with col_a:
                edit_date = st.date_input(
                    "Trade Date",
                    value=selected_row["trade_time"].date(),
                    key="edit_date",
                )
                row_action = selected_row.get("action", "Trade")
                if row_action not in ["Trade", "Deposit", "Withdraw"]:
                    row_action = "Trade"
                edit_action = st.selectbox(
                    "Action Type",
                    options=["Trade", "Deposit", "Withdraw"],
                    index=["Trade", "Deposit", "Withdraw"].index(row_action),
                    key="edit_action",
                )

            symbol_options = sorted([
                s for s in db.trades.distinct("symbol", {"user": active_user})
                if s and s.upper() != "CASH"
            ])

            edit_type   = ""
            edit_symbol = "CASH"
            edit_amount = abs(float(selected_row["pnl"]))

            with col_b:
                if edit_action == "Trade":
                    edit_type = st.selectbox(
                        "Direction",
                        options=["Long", "Short"],
                        index=0 if selected_row.get("type", "Long") == "Long" else 1,
                        key="edit_type",
                    )
                    sym_opts = (["Custom…"] + symbol_options) if symbol_options else ["Custom…"]
                    cur_sym  = selected_row["symbol"]
                    sym_idx  = (
                        symbol_options.index(cur_sym) + 1
                        if cur_sym in symbol_options else 0
                    )
                    edit_sym_choice = st.selectbox(
                        "Symbol",
                        options=sym_opts,
                        index=sym_idx,
                        key="edit_sym",
                    )
                    edit_custom = ""
                    if edit_sym_choice == "Custom…":
                        edit_custom = st.text_input(
                            "Custom Symbol",
                            value=cur_sym,
                            key="edit_csym",
                        )
                    edit_symbol = edit_custom if edit_sym_choice == "Custom…" else edit_sym_choice
                    edit_amount = st.number_input(
                        "Realised P&L ($)",
                        value=float(selected_row["pnl"]),
                        step=1.0,
                        key="edit_pnl",
                    )
                else:
                    edit_amount = st.number_input(
                        "Amount ($)",
                        min_value=0.0,
                        value=abs(float(selected_row["pnl"])),
                        step=1.0,
                        key="edit_amt",
                    )

            st.markdown('<div style="height:0.25rem;"></div>', unsafe_allow_html=True)
            btn_update, btn_delete, _ = st.columns([1, 1, 2], gap="small")

            with btn_update:
                if st.button("Save Changes", type="primary", key="btn_update"):
                    if edit_action == "Trade" and not str(edit_symbol).strip():
                        st.warning("Please enter a symbol.")
                    else:
                        pnl_val = float(edit_amount)
                        if edit_action == "Withdraw":
                            pnl_val = -abs(pnl_val)
                        db.trades.update_one(
                            {"_id": ObjectId(selected_row["id_str"]), "user": active_user},
                            {"$set": {
                                "trade_time":  datetime.combine(edit_date, dtime(0, 0)),
                                "action":      edit_action,
                                "type":        edit_type if edit_action == "Trade" else "",
                                "symbol":      str(edit_symbol).strip().upper(),
                                "pnl":         pnl_val,
                                "updated_at":  datetime.utcnow(),
                            }},
                        )
                        st.success("Trade updated successfully.")
                        st.rerun()

            with btn_delete:
                if st.button("Delete Trade", type="secondary", key="btn_delete"):
                    db.trades.delete_one(
                        {"_id": ObjectId(selected_row["id_str"]), "user": active_user}
                    )
                    st.success("Trade deleted.")
                    st.rerun()