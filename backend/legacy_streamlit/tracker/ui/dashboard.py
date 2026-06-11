"""
dashboard.py — Trading Performance Tracker
Design: Professional exchange-grade UI (TradingView × Binance Pro aesthetic).
Typography: IBM Plex Sans + IBM Plex Mono.
All original functionality preserved.
"""
from datetime import datetime, time as dtime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from tracker.services import (
    add_asset,
    add_trade,
    equity_curve,
    get_account,
    get_accounts,
    load_assets,
    load_trades,
    upsert_account,
)

try:
    import yfinance as yf
except Exception:
    yf = None

TROY_OZ_PER_GRAM = 1 / 31.1034768

# ─── Design tokens ─────────────────────────────────────────────────────────────
# Palette: TradingView dark + Binance green/red
T = {
    "bg":        "#0b0e17",   # deepest background
    "surface":   "#131722",   # card surface
    "elevated":  "#1a2035",   # inputs, tooltips
    "border":    "#232b3e",   # subtle borders
    "border2":   "#2d3a52",   # hover / focus borders
    "text":      "#eaecef",   # primary text
    "text2":     "#848e9c",   # secondary / labels
    "text3":     "#4a5568",   # placeholder / muted
    "pos":       "#0ecb81",   # Binance green
    "neg":       "#f6465d",   # Binance red
    "gold":      "#f0b90b",   # Binance yellow accent
    "blue":      "#1677ff",   # info / link blue
    "pos_bg":    "rgba(14,203,129,0.08)",
    "neg_bg":    "rgba(246,70,93,0.08)",
}

# ─── Global CSS ────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

/* ── base reset ────────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: 'IBM Plex Sans', sans-serif;
  -webkit-font-smoothing: antialiased;
}
.stApp {
  background: #0b0e17 !important;
}
.block-container {
  padding: 0 2.25rem 5rem 2.25rem !important;
  max-width: 1480px !important;
}
header[data-testid="stHeader"],
footer, #MainMenu, .stDeployButton { display: none !important; }

/* ── scrollbar ─────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0b0e17; }
::-webkit-scrollbar-thumb { background: #232b3e; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2d3a52; }

/* ── nav bar ───────────────────────────────────────────────────────────────── */
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

/* ── section label ─────────────────────────────────────────────────────────── */
.section-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #848e9c;
  margin-bottom: 0.9rem;
}
.section-divider {
  border: none;
  border-top: 1px solid #232b3e;
  margin: 0 0 0.9rem 0;
}

/* ── card ──────────────────────────────────────────────────────────────────── */
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

/* ── KPI grid ──────────────────────────────────────────────────────────────── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: #232b3e;
  border: 1px solid #232b3e;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1rem;
}
.kpi-cell {
  background: #131722;
  padding: 1.1rem 1.3rem;
}
.kpi-cell:hover { background: #161d2e; }
.kpi-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.65rem;
  font-weight: 400;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #848e9c;
  margin-bottom: 0.45rem;
}
.kpi-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.35rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.01em;
  line-height: 1.1;
}
.kpi-num.pos { color: #0ecb81; }
.kpi-num.neg { color: #f6465d; }
.kpi-sub {
  font-size: 0.72rem;
  color: #4a5568;
  margin-top: 0.35rem;
}

/* ── chart header ──────────────────────────────────────────────────────────── */
.ch-wrap {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}
.ch-left {}
.ch-price {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 2rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.02em;
  line-height: 1;
}
.ch-change {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8rem;
  font-weight: 500;
  margin-top: 0.35rem;
}
.ch-change.pos { color: #0ecb81; }
.ch-change.neg { color: #f6465d; }
.ch-meta {
  display: flex;
  gap: 1.5rem;
  margin-top: 0.55rem;
  padding-top: 0.55rem;
  border-top: 1px solid #232b3e;
}
.ch-meta-item { display: flex; flex-direction: column; gap: 2px; }
.ch-meta-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #4a5568;
}
.ch-meta-val {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8rem;
  font-weight: 500;
  color: #848e9c;
}

/* ── range radio ───────────────────────────────────────────────────────────── */
div[data-testid="stRadio"] > label { display: none !important; }
div[data-testid="stRadio"] > div {
  display: flex !important;
  flex-direction: row !important;
  gap: 0 !important;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  width: fit-content !important;
}
div[data-testid="stRadio"] > div > label {
  display: flex !important;
  align-items: center !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.7rem !important;
  font-weight: 400 !important;
  letter-spacing: 0.04em !important;
  padding: 4px 10px !important;
  border-radius: 0 !important;
  cursor: pointer !important;
  color: #848e9c !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  background: transparent !important;
  transition: all 0.12s !important;
}
div[data-testid="stRadio"] > div > label:hover {
  color: #eaecef !important;
}
div[data-testid="stRadio"] > div > label[data-baseweb="radio"]:has(input:checked) {
  color: #eaecef !important;
  border-bottom-color: #0ecb81 !important;
  font-weight: 500 !important;
}
div[data-testid="stRadio"] input[type="radio"] { display: none !important; }
div[data-testid="stRadio"] > div > label > div:first-child { display: none !important; }

/* ── form labels & inputs ──────────────────────────────────────────────────── */
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
/* date input */
div[data-testid="stDateInput"] input {
  background: #1a2035 !important;
  border: 1px solid #232b3e !important;
  border-radius: 6px !important;
  color: #eaecef !important;
  font-family: 'IBM Plex Mono', monospace !important;
}

/* ── buttons ───────────────────────────────────────────────────────────────── */
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

/* ── expander ──────────────────────────────────────────────────────────────── */
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

/* ── dataframe ─────────────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] > div {
  border-radius: 6px !important;
  border: 1px solid #232b3e !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.78rem !important;
}

/* ── alerts & messages ─────────────────────────────────────────────────────── */
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
div[data-testid="stErrorAlert"] {
  background: rgba(246,70,93,0.07) !important;
  border-left-color: #f6465d !important;
  color: #f6465d !important;
}

/* ── risk metric block ─────────────────────────────────────────────────────── */
.risk-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: #232b3e;
  border: 1px solid #232b3e;
  border-radius: 6px;
  overflow: hidden;
  margin-top: 0.75rem;
}
.risk-cell {
  background: #131722;
  padding: 0.9rem 1rem;
}
.risk-lbl {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.62rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #4a5568;
  margin-bottom: 0.3rem;
}
.risk-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.1rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.01em;
}
.risk-hint {
  font-size: 0.68rem;
  color: #4a5568;
  margin-top: 0.2rem;
}

/* ── divider util ──────────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid #232b3e !important; margin: 1rem 0 !important; }

/* ── account badge ─────────────────────────────────────────────────────────── */
.acct-badge {
  display: inline-block;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.6rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 3px;
  vertical-align: middle;
  margin-left: 8px;
}

/* ── table row pair header ─────────────────────────────────────────────────── */
.tbl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
</style>
"""

# ─── Plotly chart base layout ──────────────────────────────────────────────────
_CHART_CFG = dict(displayModeBar=False, scrollZoom=False, responsive=True)
_CHART_LAY = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'IBM Plex Mono', monospace", color="#848e9c", size=10),
    margin=dict(l=0, r=0, t=8, b=0),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor="#1a2035",
        bordercolor="#232b3e",
        font=dict(family="'IBM Plex Mono', monospace", color="#eaecef", size=11),
    ),
    xaxis=dict(
        showgrid=False, zeroline=False, showline=False,
        tickfont=dict(color="#4a5568", size=9),
        tickformat="%d %b %Y",
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(35,43,62,0.9)",
        zeroline=False, showline=False,
        tickfont=dict(color="#4a5568", size=9),
        tickprefix="$",
        tickformat=",.2f",
        side="right",
    ),
)

_RANGE_OPTIONS: dict[str, int | None] = {
    "1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "ALL": None,
}
_FALLBACK_MAP = {"XAUUSD=X": "GC=F", "XAGUSD=X": "SI=F"}


# ─── Formatting helpers ────────────────────────────────────────────────────────

def _money(v: float, always_sign: bool = False) -> str:
    """Full-precision monetary string, e.g. $12,345.67"""
    sign = ""
    if always_sign:
        sign = "+" if v >= 0 else ""
    return f"{sign}${v:,.2f}"


def _pct(v: float, always_sign: bool = True) -> str:
    sign = "+" if v >= 0 and always_sign else ""
    return f"{sign}{v:.2f}%"


def _to_utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, errors="coerce")


def _clip_range(df: pd.DataFrame, days: int | None, col: str = "trade_time") -> pd.DataFrame:
    if df.empty or days is None:
        return df
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    return df[_to_utc(df[col]) >= cutoff]


def _build_fetch_list(syms: list[str]) -> list[str]:
    out = set(syms)
    for s in syms:
        if s in _FALLBACK_MAP:
            out.add(_FALLBACK_MAP[s])
    return sorted(out)


@st.cache_data(show_spinner=False, ttl=3600)
def _yf_prices(symbols: tuple, period: str) -> pd.DataFrame:
    data = yf.download(
        tickers=" ".join(symbols), period=period,
        interval="1d", auto_adjust=True, progress=False,
    )
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) \
        else data[["Close"]].rename(columns={"Close": symbols[0]})
    return close.ffill()


def _resolve_series(prices: pd.DataFrame, sym: str):
    s = prices.get(sym)
    if s is None or (hasattr(s, "isna") and s.isna().all()):
        alt = _FALLBACK_MAP.get(sym)
        return prices[alt] if alt and alt in prices.columns else None
    return s


# ─── KPI computation ───────────────────────────────────────────────────────────

def _compute_kpis(trades_df: pd.DataFrame, starting_bal: float) -> dict:
    total_pnl  = float(trades_df["pnl"].sum()) if not trades_df.empty else 0.0
    trade_rows = trades_df[trades_df["action"] == "Trade"] if not trades_df.empty else pd.DataFrame()
    n          = len(trade_rows)
    n_wins     = int((trade_rows["pnl"] > 0).sum()) if not trade_rows.empty else 0
    win_rate   = n_wins / n * 100 if n > 0 else 0.0
    best       = float(trade_rows["pnl"].max()) if not trade_rows.empty else 0.0
    avg_pnl    = float(trade_rows["pnl"].mean()) if not trade_rows.empty else 0.0
    return {
        "balance":  starting_bal + total_pnl,
        "pnl":      total_pnl,
        "win_rate": win_rate,
        "best":     best,
        "avg":      avg_pnl,
        "n_trades": n,
        "n_wins":   n_wins,
    }


def _kpi_html(k: dict) -> str:
    pnl_cls = "pos" if k["pnl"] >= 0 else "neg"
    win_cls = "pos" if k["win_rate"] >= 50 else "neg"
    best_cls = "pos" if k["best"] >= 0 else "neg"
    avg_cls  = "pos" if k["avg"] >= 0 else "neg"
    return f"""
<div class="kpi-row">
  <div class="kpi-cell">
    <div class="kpi-lbl">Account Balance</div>
    <div class="kpi-num">{_money(k['balance'])}</div>
    <div class="kpi-sub">Starting capital + realised P&amp;L</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-lbl">Total Realised P&amp;L</div>
    <div class="kpi-num {pnl_cls}">{_money(k['pnl'], always_sign=True)}</div>
    <div class="kpi-sub">{k['n_trades']} trade{'s' if k['n_trades']!=1 else ''} &nbsp;·&nbsp; {k['n_wins']} winning</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-lbl">Win Rate</div>
    <div class="kpi-num {win_cls}">{k['win_rate']:.1f}%</div>
    <div class="kpi-sub">{k['n_wins']} wins out of {k['n_trades']} closed trades</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-lbl">Average Trade P&amp;L</div>
    <div class="kpi-num {avg_cls}">{_money(k['avg'], always_sign=True)}</div>
    <div class="kpi-sub">Best single trade: {_money(k['best'])}</div>
  </div>
</div>"""


# ─── Equity chart ──────────────────────────────────────────────────────────────

def _render_equity_chart(
    trades_df: pd.DataFrame,
    accounts_map: dict,
    accounts_created: dict,
    selected_accounts: list,
    selected_account: str,
    starting_bal: float,
) -> None:
    if trades_df.empty:
        st.info("No trades recorded yet. Add your first trade using the panel on the right.")
        return

    # Range selector — tab-style underline (no pill borders)
    rng = st.radio(
        "_rng", list(_RANGE_OPTIONS.keys()),
        index=5, horizontal=True, label_visibility="collapsed", key="eq_range",
    )
    days = _RANGE_OPTIONS[rng]

    fil = trades_df.copy()
    fil["trade_time"] = _to_utc(fil["trade_time"])
    fil = _clip_range(fil, days)
    if fil.empty:
        st.info(f"No trades in the selected period ({rng}).")
        return

    curve = equity_curve(fil, accounts_map, accounts_created)
    if curve.empty:
        st.info("Could not compute equity curve for the selected range.")
        return

    if len(selected_accounts) > 1:
        curve = curve.groupby("trade_time", as_index=False)["balance"].sum()
    else:
        curve = curve[["trade_time", "balance"]].copy()
    curve = curve.sort_values("trade_time").reset_index(drop=True)

    s_bal = float(curve["balance"].iloc[0])
    e_bal = float(curve["balance"].iloc[-1])
    delta = e_bal - s_bal
    dpct  = delta / s_bal * 100 if s_bal else 0.0
    ipos  = delta >= 0
    dcls  = "pos" if ipos else "neg"
    arrow = "▲" if ipos else "▼"
    hi    = float(curve["balance"].max())
    lo    = float(curve["balance"].min())
    n_pts = len(fil)

    accent = T["pos"] if ipos else T["neg"]
    fill   = T["pos_bg"] if ipos else T["neg_bg"]

    st.markdown(f"""
    <div class="ch-wrap">
      <div class="ch-left">
        <div class="ch-price">{_money(e_bal)}</div>
        <div class="ch-change {dcls}">
          {arrow}&nbsp;{_money(delta, always_sign=True)}&nbsp;&nbsp;{_pct(dpct)}
          <span style="color:{T['text3']};font-size:0.68rem;font-weight:400;">&nbsp;{rng}</span>
        </div>
      </div>
    </div>
    <div class="ch-meta">
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Period High</span>
        <span class="ch-meta-val">{_money(hi)}</span>
      </div>
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Period Low</span>
        <span class="ch-meta-val">{_money(lo)}</span>
      </div>
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Opening Balance</span>
        <span class="ch-meta-val">{_money(s_bal)}</span>
      </div>
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Entries</span>
        <span class="ch-meta-val">{n_pts}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve["trade_time"], y=curve["balance"],
        mode="lines",
        line=dict(width=1.75, color=accent, shape="spline", smoothing=0.6),
        fill="tozeroy",
        fillcolor=fill,
        hovertemplate="%{x|%d %b %Y}  <b>$%{y:,.2f}</b><extra></extra>",
        showlegend=False,
    ))
    lay = dict(**_CHART_LAY, height=270)
    lay["yaxis"] = dict(**_CHART_LAY["yaxis"], range=[max(0, lo * 0.97), hi * 1.04])
    fig.update_layout(**lay)
    st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)


# ─── Risk calculator ───────────────────────────────────────────────────────────

def _render_risk_calculator(
    selected_account: str,
    accounts_map: dict,
    trades_all: pd.DataFrame,
) -> None:
    bal = float(accounts_map.get(selected_account, 0.0))
    if not trades_all.empty:
        bal += float(trades_all[trades_all["account"] == selected_account]["pnl"].sum())

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        portfolio  = st.number_input("Portfolio Balance ($)", min_value=0.0, value=max(bal, 0.0), step=100.0, key="rk_port")
        risk_pct   = st.number_input("Risk Per Trade (%)", min_value=0.01, value=1.0, step=0.1, key="rk_rp")
        stop_pct   = st.number_input("Stop Loss (%)", min_value=0.01, value=2.0, step=0.1, key="rk_sl")
    with c2:
        leverage   = st.number_input("Leverage (×)", min_value=1, value=3, step=1, key="rk_lev")
        rr         = st.number_input("Risk / Reward Ratio", min_value=0.1, value=2.0, step=0.1, key="rk_rr")

    if (stop_pct * leverage) <= 0:
        st.warning("Stop loss and leverage must both be greater than zero.")
        return

    risk_val = float(portfolio) * float(risk_pct) / 100
    act_loss = float(stop_pct) * float(leverage)
    margin   = risk_val * (100 / act_loss)
    pos_size = margin * float(leverage)
    pot_gain = risk_val * float(rr)

    st.markdown(f"""
    <div class="risk-row">
      <div class="risk-cell">
        <div class="risk-lbl">Recommended Margin</div>
        <div class="risk-num">{_money(margin)}</div>
        <div class="risk-hint">Capital to commit at {leverage}× leverage</div>
      </div>
      <div class="risk-cell">
        <div class="risk-lbl">Total Position Size</div>
        <div class="risk-num">{_money(pos_size)}</div>
        <div class="risk-hint">Full notional exposure</div>
      </div>
      <div class="risk-cell">
        <div class="risk-lbl">Maximum Loss</div>
        <div class="risk-num" style="color:{T['neg']};">{_money(risk_val)}</div>
        <div class="risk-hint">{act_loss:.2f}% adverse move triggers stop</div>
      </div>
      <div class="risk-cell">
        <div class="risk-lbl">Target Profit</div>
        <div class="risk-num" style="color:{T['pos']};">{_money(pot_gain)}</div>
        <div class="risk-hint">At {rr:.1f}R — take-profit level</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Overall (multi-account net worth) view ────────────────────────────────────

def _render_overall(db, active_user: str, accounts_map: dict) -> None:
    accounts         = get_accounts(db, active_user)
    trading_names    = [a["name"] for a in accounts if a.get("type") in ["Trading", "Bank Account"]]
    investing_names  = [a["name"] for a in accounts if a.get("type") == "Investing"]
    accounts_map_all = {a["name"]: a.get("starting_balance", 0.0) for a in accounts}
    accounts_cr_all  = {a["name"]: a.get("created_at") for a in accounts}

    period_opts = [
        ("1 Week","1wk"),("1 Month","1mo"),("3 Months","3mo"),
        ("6 Months","6mo"),("1 Year","1y"),("3 Years","3y"),("All Time","max"),
    ]
    offsets = {
        "1wk": pd.DateOffset(weeks=1),  "1mo": pd.DateOffset(months=1),
        "3mo": pd.DateOffset(months=3), "6mo": pd.DateOffset(months=6),
        "1y":  pd.DateOffset(years=1),  "3y":  pd.DateOffset(years=3),
    }
    p_sel  = st.selectbox("Period", options=period_opts, index=4, format_func=lambda x: x[0], key="ov_period")
    period = p_sel[1]

    # ── Trading curve ──
    trades_all = load_trades(db, trading_names, active_user)
    if period != "max" and not trades_all.empty:
        trades_all["trade_time"] = _to_utc(trades_all["trade_time"])
        cutoff = pd.Timestamp.now(tz="UTC") - offsets[period]
        trades_all = trades_all[trades_all["trade_time"] >= cutoff]

    trade_curve = pd.DataFrame()
    if not trades_all.empty:
        c = equity_curve(trades_all, accounts_map_all, accounts_cr_all)
        c = c.groupby("trade_time", as_index=False)["balance"].sum()
        c["trade_time"] = _to_utc(c["trade_time"])
        trade_curve = c.set_index("trade_time").sort_index()

    # ── Investing curve ──
    invest_curve = pd.DataFrame()
    if investing_names and yf is not None:
        all_dfs = [load_assets(db, acc, active_user) for acc in investing_names]
        all_assets = pd.concat([d for d in all_dfs if not d.empty], ignore_index=True) if all_dfs else pd.DataFrame()
        if not all_assets.empty:
            syms   = sorted({s.upper() for s in all_assets["symbol"] if s})
            fetch  = _build_fetch_list(syms)
            prices = _yf_prices(tuple(fetch), period)
            qty_map = all_assets.groupby("symbol")["quantity"].sum()
            aligned = pd.DataFrame(index=prices.index)
            for sym in syms:
                s = _resolve_series(prices, sym)
                if s is not None:
                    aligned[sym] = s * float(qty_map.get(sym, 0.0))
            aligned["invest"] = aligned.sum(axis=1)
            invest_curve = aligned[["invest"]].copy()
            if invest_curve.index.tz is None:
                invest_curve.index = invest_curve.index.tz_localize("UTC")

    # ── Combine ──
    combined = pd.DataFrame()
    if not trade_curve.empty:
        combined = trade_curve.rename(columns={"balance": "trade"})
    if not invest_curve.empty:
        combined = combined.join(invest_curve, how="outer") if not combined.empty else invest_curve.copy()
    if combined.empty:
        st.info("No data available. Create accounts and log trades to see your net worth chart.")
        return

    combined = combined.sort_index().ffill()
    combined["total"] = combined.sum(axis=1)
    cdf = combined.reset_index().rename(columns={"index": "trade_time"})

    t_now   = float(cdf["total"].iloc[-1])
    t_start = float(cdf["total"].iloc[0])
    delta   = t_now - t_start
    dpct    = delta / t_start * 100 if t_start else 0.0
    ipos    = delta >= 0
    dcls    = "pos" if ipos else "neg"
    arrow   = "▲" if ipos else "▼"
    accent  = T["pos"] if ipos else T["neg"]
    fill    = T["pos_bg"] if ipos else T["neg_bg"]
    hi      = float(cdf["total"].max())
    lo      = float(cdf["total"].min())

    st.markdown(f"""
    <div class="ch-wrap">
      <div class="ch-left">
        <div class="ch-price">{_money(t_now)}</div>
        <div class="ch-change {dcls}">{arrow}&nbsp;{_money(delta, always_sign=True)}&nbsp;&nbsp;{_pct(dpct)}</div>
      </div>
    </div>
    <div class="ch-meta">
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Period High</span>
        <span class="ch-meta-val">{_money(hi)}</span>
      </div>
      <div class="ch-meta-item">
        <span class="ch-meta-lbl">Period Low</span>
        <span class="ch-meta-val">{_money(lo)}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cdf["trade_time"], y=cdf["total"],
        mode="lines",
        line=dict(width=1.75, color=accent, shape="spline", smoothing=0.6),
        fill="tozeroy", fillcolor=fill,
        hovertemplate="%{x|%d %b %Y}  <b>$%{y:,.2f}</b><extra></extra>",
        showlegend=False,
    ))
    lay = dict(**_CHART_LAY, height=270)
    lay["yaxis"] = dict(**_CHART_LAY["yaxis"], range=[max(0, lo * 0.97), hi * 1.04])
    fig.update_layout(**lay)
    st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)

    # ── Account balances table ──
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Account Balances</div>', unsafe_allow_html=True)
    rows = []
    for acc in trading_names:
        t   = load_trades(db, [acc], active_user)
        b   = accounts_map.get(acc, 0.0) + (float(t["pnl"].sum()) if not t.empty else 0.0)
        rows.append({"Account": acc, "Type": "Trading / Bank", "Balance": f"${b:,.2f}"})

    if investing_names and yf is not None:
        adf_list = []
        for acc in investing_names:
            df = load_assets(db, acc, active_user)
            if not df.empty:
                df = df.copy(); df["account"] = acc; adf_list.append(df)
        if adf_list:
            adf    = pd.concat(adf_list, ignore_index=True)
            syms   = sorted({s.upper() for s in adf["symbol"] if s})
            fetch  = _build_fetch_list(syms)
            closes = _yf_prices(tuple(fetch), "1mo")
            latest = closes.iloc[-1] if not closes.empty else pd.Series(dtype=float)
            for acc in investing_names:
                sub   = adf[adf["account"] == acc]
                total = sum(
                    float(latest.get(r["symbol"], latest.get(_FALLBACK_MAP.get(r["symbol"], ""), 0.0)) or 0.0)
                    * float(r["quantity"]) for _, r in sub.iterrows()
                )
                rows.append({"Account": acc, "Type": "Investing", "Balance": f"${total:,.2f}"})

    if rows:
        grand = sum(float(r["Balance"].replace("$","").replace(",","")) for r in rows)
        rows.append({"Account": "TOTAL", "Type": "—", "Balance": f"${grand:,.2f}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─── Investing account view ────────────────────────────────────────────────────

def _render_investing(db, active_user: str, selected_account: str) -> None:
    if yf is None:
        st.error("yfinance is not installed. Run: pip install yfinance")
        return

    assets_df = load_assets(db, selected_account, active_user)

    # ── Current portfolio value ──
    total_val = 0.0
    if not assets_df.empty:
        syms  = sorted({s.upper() for s in assets_df["symbol"] if s})
        fetch = _build_fetch_list(syms)
        try:
            closes  = _yf_prices(tuple(fetch), "1mo")
            latest  = closes.iloc[-1] if not closes.empty else pd.Series(dtype=float)
            qty_map = assets_df.groupby("symbol")["quantity"].sum()
            for sym in syms:
                p = float(latest.get(sym, latest.get(_FALLBACK_MAP.get(sym, ""), 0.0)) or 0.0)
                total_val += p * float(qty_map.get(sym, 0.0))
        except Exception:
            pass

    # ── KPI strip (2 cells) ──
    st.markdown(f"""
    <div class="kpi-row" style="grid-template-columns:1fr 1fr;max-width:560px;">
      <div class="kpi-cell">
        <div class="kpi-lbl">Portfolio Market Value</div>
        <div class="kpi-num">{_money(total_val)}</div>
        <div class="kpi-sub">Based on latest closing prices</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-lbl">Assets Held</div>
        <div class="kpi-num">{len(assets_df)}</div>
        <div class="kpi-sub">Open positions in this account</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Portfolio value chart ──
    if not assets_df.empty:
        period_opts = [
            ("1 Year","1y"),("3 Years","3y"),("5 Years","5y"),("All Time","max"),
        ]
        p_sel  = st.selectbox("Time Range", options=period_opts, format_func=lambda x: x[0], key="inv_period")
        period = p_sel[1]

        syms    = sorted({s.upper() for s in assets_df["symbol"] if s})
        fetch   = _build_fetch_list(syms)
        prices  = _yf_prices(tuple(fetch), period)
        qty_map = assets_df.groupby("symbol")["quantity"].sum()

        aligned = pd.DataFrame(index=prices.index)
        for sym in syms:
            s = _resolve_series(prices, sym)
            if s is not None:
                aligned[sym] = s * float(qty_map.get(sym, 0.0))
        aligned["balance"] = aligned.sum(axis=1)
        cdf = aligned.reset_index().rename(columns={"index": "trade_time", "Date": "trade_time"})

        hi = float(cdf["balance"].max()); lo = float(cdf["balance"].min())

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(
            x=cdf["trade_time"], y=cdf["balance"],
            name="Total Value",
            line=dict(width=1.75, color=T["pos"], shape="spline", smoothing=0.6),
            fill="tozeroy", fillcolor=T["pos_bg"],
            hovertemplate="%{x|%d %b %Y}  <b>$%{y:,.2f}</b><extra></extra>",
        ), secondary_y=False)

        asset_colors = ["#f0b90b", "#1677ff", "#a855f7", "#f97316", "#14b8a6", "#e11d48"]
        for i, sym in enumerate([c for c in aligned.columns if c != "balance"]):
            fig.add_trace(go.Scatter(
                x=aligned.index, y=aligned[sym], name=sym,
                line=dict(width=1.25, color=asset_colors[i % len(asset_colors)]),
                opacity=0.6,
                hovertemplate=f"{sym}  <b>$%{{y:,.2f}}</b><extra></extra>",
            ), secondary_y=True)

        lay = dict(**_CHART_LAY, height=290, showlegend=True,
                   legend=dict(font=dict(color=T["text2"], size=9, family="IBM Plex Mono"),
                               bgcolor="rgba(0,0,0,0)", x=0.01, y=0.99))
        lay["yaxis"] = dict(**_CHART_LAY["yaxis"], range=[max(0, lo * 0.97), hi * 1.04])
        fig.update_layout(**lay)
        fig.update_yaxes(showgrid=False, zeroline=False, secondary_y=True,
                         tickfont=dict(color=T["text3"], size=9), tickprefix="$", tickformat=",.2f")
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Add asset (left) + Holdings table (right) ──
    left, right = st.columns([1, 1.6], gap="large")
    with left:
        st.markdown('<div class="section-label">Add New Asset</div>', unsafe_allow_html=True)
        preset_map = {
            "Gold": "XAUUSD=X", "Silver": "XAGUSD=X", "Copper": "HG=F",
            "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD",
            "S&P 500 (SPX)": "^GSPC", "Custom…": "",
        }
        preset = st.selectbox("Asset", options=list(preset_map.keys()), key="inv_preset")
        sym    = preset_map.get(preset, "")
        if preset == "Custom…":
            sym = st.text_input("Ticker Symbol", placeholder="e.g. AAPL, MSFT", key="inv_csym")
        unit = "units"
        if preset in ["Gold", "Silver", "Copper"]:
            unit = st.selectbox("Weight Unit", options=["oz (troy)", "g"], key="inv_unit")
            unit = "oz" if unit.startswith("oz") else "g"
        qty = st.number_input(
            "Quantity", min_value=0.0, value=0.0,
            step=0.001, format="%.6f", key="inv_qty",
        )
        if st.button("Add Asset", type="primary", key="btn_add_asset"):
            if not sym.strip():
                st.warning("Please enter a ticker symbol.")
            else:
                qty_base = float(qty) * (TROY_OZ_PER_GRAM if unit == "g" else 1.0)
                add_asset(db, {
                    "account": selected_account,
                    "symbol": sym.strip().upper(),
                    "quantity": qty_base,
                    "unit": unit,
                    "display_quantity": float(qty),
                    "created_at": datetime.utcnow(),
                }, active_user)
                st.success("Asset added successfully.")
                st.rerun()

    with right:
        st.markdown('<div class="section-label">Holdings</div>', unsafe_allow_html=True)
        if assets_df.empty:
            st.info("No assets added yet.")
        else:
            view = assets_df.copy()
            view["symbol"] = view["symbol"].str.upper()
            view["quantity"] = view["quantity"].astype(float)
            if "unit" not in view.columns:
                view["unit"] = "units"
            if "display_quantity" not in view.columns:
                view["display_quantity"] = view["quantity"]
            else:
                view["display_quantity"] = view["display_quantity"].fillna(view["quantity"])

            def _display_qty(row):
                if row["unit"] == "g" and row["display_quantity"] == row["quantity"]:
                    return row["quantity"] / TROY_OZ_PER_GRAM
                return row["display_quantity"]

            view["display_quantity"] = view.apply(_display_qty, axis=1)
            view["current_value"] = 0.0
            try:
                syms_v  = sorted({s for s in view["symbol"] if s})
                fetch_v = _build_fetch_list(syms_v)
                closes  = _yf_prices(tuple(fetch_v), "1mo")
                latest  = closes.iloc[-1] if not closes.empty else pd.Series(dtype=float)
                view["current_value"] = view.apply(
                    lambda r: float(
                        latest.get(r["symbol"],
                            latest.get(_FALLBACK_MAP.get(r["symbol"], ""), 0.0)) or 0.0
                    ) * float(r["quantity"]),
                    axis=1,
                )
            except Exception:
                pass

            display = view[["symbol", "display_quantity", "unit", "current_value"]].copy()
            display.columns = ["Symbol", "Quantity", "Unit", "Market Value ($)"]
            display["Market Value ($)"] = display["Market Value ($)"].apply(lambda v: f"${v:,.2f}")
            st.dataframe(display, use_container_width=True, hide_index=True)

            st.markdown(
                f'<div style="text-align:right;font-family:IBM Plex Mono,monospace;'
                f'font-size:0.78rem;color:{T["text2"]};padding:0.4rem 0;">'
                f'Total Market Value &nbsp;<span style="color:{T["text"]};font-weight:600;">'
                f'{_money(total_val)}</span></div>',
                unsafe_allow_html=True,
            )


# ─── Main render function ──────────────────────────────────────────────────────

def render_dashboard(db):
    st.markdown(_CSS, unsafe_allow_html=True)

    active_user = st.session_state.get("auth_user")
    if not active_user:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;'
            f'height:60vh;font-family:IBM Plex Mono,monospace;font-size:0.85rem;'
            f'color:{T["text2"]};">Please log in to access your dashboard.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Account data ──
    existing_accounts = get_accounts(db, active_user)
    existing_names    = [a["name"] for a in existing_accounts]
    accounts_map      = {a["name"]: a.get("starting_balance", 0.0) for a in existing_accounts}
    accounts_created  = {a["name"]: a.get("created_at") for a in existing_accounts}

    # ══════════════════════════════════════════════════════════════════════════
    #  NAV BAR
    #  Brand (left) | Account selector (center) | New Account expander (right)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
    col_brand, col_sel, col_new = st.columns([1, 2.5, 1.2], gap="medium")

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
            key="main_acct",
        )

    with col_new:
        st.markdown('<div style="padding-top:1.05rem;"></div>', unsafe_allow_html=True)
        with st.expander("＋  New Account"):
            acc_name  = st.text_input("Account Name", placeholder="e.g. Binance Spot", key="na_name")
            acc_type  = st.selectbox(
                "Account Type",
                options=["Trading", "Investing", "Bank Account", "Overall"],
                key="na_type",
            )
            acc_start = st.number_input(
                "Starting Balance ($)", min_value=0.0, value=0.0, step=100.0, key="na_bal",
            )
            if st.button("Create Account", type="primary", key="btn_create"):
                if not acc_name.strip():
                    st.warning("Please enter an account name.")
                else:
                    upsert_account(db, active_user, acc_name.strip(), float(acc_start), acc_type)
                    st.success("Account created successfully.")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # close nav-wrap
    st.markdown('<div style="height:1.5rem;"></div>', unsafe_allow_html=True)

    if not selected_account:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:center;height:50vh;'
            f'font-family:IBM Plex Mono,monospace;font-size:0.82rem;color:{T["text2"]};">'
            'Select or create an account to get started.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Resolve account metadata ──
    account_record = get_account(db, active_user, selected_account) or {}
    account_type   = account_record.get("type", "Trading")
    starting_bal   = float(accounts_map.get(selected_account, 0.0))
    selected_accounts = [selected_account]

    # ── Account heading ──
    badge_colors = {
        "Trading":      (T["pos"],  "rgba(14,203,129,0.1)"),
        "Investing":    (T["gold"], "rgba(240,185,11,0.1)"),
        "Bank Account": (T["blue"], "rgba(22,119,255,0.1)"),
        "Overall":      ("#a855f7", "rgba(168,85,247,0.1)"),
    }
    badge_fg, badge_bg = badge_colors.get(account_type, (T["text2"], T["elevated"]))
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:1.1rem;">'
        f'<span style="font-family:IBM Plex Mono,monospace;font-size:1.15rem;font-weight:600;'
        f'color:{T["text"]};letter-spacing:-0.01em;">{selected_account}</span>'
        f'<span class="acct-badge" style="background:{badge_bg};color:{badge_fg};">{account_type}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    #  OVERALL
    # ══════════════════════════════════════════════════════════════════════════
    if account_type == "Overall":
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Net Worth — All Accounts</div>', unsafe_allow_html=True)
            _render_overall(db, active_user, accounts_map)
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # ══════════════════════════════════════════════════════════════════════════
    #  INVESTING
    # ══════════════════════════════════════════════════════════════════════════
    if account_type == "Investing":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Portfolio Performance</div>', unsafe_allow_html=True)
        _render_investing(db, active_user, selected_account)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ══════════════════════════════════════════════════════════════════════════
    #  TRADING  /  BANK ACCOUNT
    # ══════════════════════════════════════════════════════════════════════════
    trades_df  = load_trades(db, selected_accounts, active_user)
    trades_all = trades_df.copy()

    symbols = db.trades.distinct("symbol", {"user": active_user}) if existing_names else []
    symbol_options = sorted([s for s in symbols if s and s.upper() != "CASH"])

    # ── KPI strip ──
    k = _compute_kpis(trades_df, starting_bal)
    st.markdown(_kpi_html(k), unsafe_allow_html=True)

    # ── Chart (left, 2.4/4) + Log Action (right, 1.6/4) ──
    chart_col, action_col = st.columns([2.4, 1.6], gap="large")

    with chart_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Balance Through Time</div>', unsafe_allow_html=True)
        _render_equity_chart(
            trades_df, accounts_map, accounts_created,
            selected_accounts, selected_account, starting_bal,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with action_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Log Action</div>', unsafe_allow_html=True)

        trade_date = st.date_input("Trade Date", value=datetime.utcnow().date(), key="act_date")
        action     = st.selectbox("Action Type", options=["Trade", "Deposit", "Withdraw"], key="act_type")

        trade_type = "Long"
        symbol     = "CASH"
        amount     = 0.0

        if action == "Trade":
            trade_type = st.selectbox("Direction", options=["Long", "Short"], key="act_dir")
            sym_opts   = (["Custom…"] + symbol_options) if symbol_options else ["Custom…"]
            sym_choice = st.selectbox("Symbol", options=sym_opts, key="act_sym")
            custom_sym = ""
            if sym_choice == "Custom…":
                custom_sym = st.text_input("Enter Ticker", placeholder="e.g. BTCUSDT", key="act_csym")
            symbol = custom_sym if sym_choice == "Custom…" else sym_choice
            amount = st.number_input("Realised P&L ($)", value=0.0, step=1.0, key="act_pnl")
        else:
            amount = st.number_input("Amount ($)", min_value=0.0, value=0.0, step=1.0, key="act_amt")

        if st.button("Submit Entry", type="primary", key="btn_log"):
            if action == "Trade" and not symbol.strip():
                st.warning("Please select or enter a symbol.")
            else:
                pnl_val = float(amount) * (-1 if action == "Withdraw" else 1)
                add_trade(db, {
                    "account":    selected_account,
                    "trade_time": datetime.combine(trade_date, dtime(0, 0)),
                    "action":     action,
                    "type":       trade_type if action == "Trade" else "",
                    "symbol":     symbol.strip().upper(),
                    "pnl":        pnl_val,
                    "notes":      "",
                    "created_at": datetime.utcnow(),
                }, active_user)
                st.success("Entry submitted.")
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Bank Account: balance summary ──
    if account_type == "Bank Account":
        cur_bal = starting_bal + (float(trades_df["pnl"].sum()) if not trades_df.empty else 0.0)
        st.markdown(f"""
        <div class="card">
          <div class="section-label">Current Account Balance</div>
          <div style="font-family:IBM Plex Mono,monospace;font-size:1.9rem;font-weight:600;
               color:{T['text']};letter-spacing:-0.02em;">{_money(cur_bal)}</div>
          <div style="font-size:0.72rem;color:{T['text3']};margin-top:0.4rem;">{selected_account}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Trading only: Calendar + Risk Calculator ──
    if account_type == "Trading":
        from tracker.ui.calendar_view import render_calendar

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Trade Calendar</div>', unsafe_allow_html=True)
        render_calendar(trades_df, selected_accounts, accounts_map, trades_all)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Position Sizing Calculator</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.75rem;color:{T["text3"]};margin-bottom:0.9rem;">'
            'Calculate optimal margin, position size, and risk/reward for a single trade.</div>',
            unsafe_allow_html=True,
        )
        _render_risk_calculator(selected_account, accounts_map, trades_all)
        st.markdown('</div>', unsafe_allow_html=True)