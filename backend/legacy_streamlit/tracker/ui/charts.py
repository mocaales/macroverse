"""
charts.py — Charts Dashboard
Design: professional trading platform style (institutional, restrained, high-density).
All original functionality preserved (sidebar nav, filters, favourites, renderer dispatch).
"""
import os

import streamlit as st
from dotenv import load_dotenv
from tracker.auth import get_user_favourites, toggle_user_favourite
from tracker.charts.registry import CHARTS, get_chart_map

# ─── Design tokens (same as dashboard.py / journal.py) ────────────────────────
_T = {
    "bg": "#0d1117",
    "surface": "#121821",
    "elevated": "#182231",
    "border": "#253247",
    "border2": "#32435f",
    "text": "#e8edf5",
    "text2": "#9aa9bf",
    "text3": "#637186",
    "pos": "#13b981",
    "neg": "#ef4444",
    "gold": "#f0b90b",
    "blue": "#3b82f6",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

/* ── base ───────────────────────────────────────────────────────────────────── */
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

/* ── sidebar ────────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: #0c121b !important;
  border-right: 1px solid #1f2b3d !important;
}
section[data-testid="stSidebar"] .block-container {
  padding: 0.95rem 0.72rem 1.8rem 0.72rem !important;
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.63rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
  color: #73839a !important;
  margin: 0 0 0.55rem 0.18rem !important;
}
section[data-testid="stSidebar"] .stSubheader {
  font-family: 'IBM Plex Mono', monospace !important;
}

/* sidebar form labels */
section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] label {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.54rem !important;
  letter-spacing: 0.11em !important;
  text-transform: uppercase !important;
  color: #536177 !important;
}
section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {
  background: #111a26 !important;
  border: 1px solid #243348 !important;
  border-radius: 5px !important;
  color: #dfe7f2 !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.75rem !important;
  min-height: 2.2rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div:focus-within,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input:focus {
  border-color: #3d5a80 !important;
  outline: none !important;
  box-shadow: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stSelectbox"],
section[data-testid="stSidebar"] div[data-testid="stTextInput"] {
  margin-bottom: 0.12rem !important;
}

/* sidebar radio (chart list) */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
  display: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
  display: flex !important;
  flex-direction: column !important;
  gap: 1px !important;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div > label {
  display: flex !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.69rem !important;
  font-weight: 400 !important;
  letter-spacing: 0.02em !important;
  padding: 0.42rem 0.58rem !important;
  border-radius: 4px !important;
  color: #7f90a7 !important;
  border: 1px solid rgba(255,255,255,0.02) !important;
  background: transparent !important;
  cursor: pointer !important;
  transition: all 0.1s !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div > label:hover {
  background: #111a26 !important;
  color: #d6e0ef !important;
  border-color: rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div > label[data-baseweb="radio"]:has(input:checked) {
  background: rgba(59, 130, 246, 0.12) !important;
  border-color: rgba(96, 165, 250, 0.38) !important;
  color: #dce9ff !important;
  font-weight: 500 !important;
  box-shadow: inset 2px 0 0 #60a5fa !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] input[type="radio"] { display: none !important; }
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div > label > div:first-child { display: none !important; }

/* sidebar divider + caption */
section[data-testid="stSidebar"] hr { border-color: #1f2b3d !important; margin: 0.75rem 0 !important; }
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] .stCaption p {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.6rem !important;
  letter-spacing: 0.03em !important;
  color: #536177 !important;
}

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
.nav-dot { width: 6px; height: 6px; background: #0ecb81; border-radius: 50%; display: inline-block; }

/* ── page heading ───────────────────────────────────────────────────────────── */
.page-title {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 1.3rem;
  font-weight: 600;
  color: #eaecef;
  letter-spacing: -0.015em;
  margin-bottom: 0.15rem;
}
.page-sub {
  font-size: 0.82rem;
  color: #7f8ea6;
  margin-bottom: 1.3rem;
}

/* ── section label ──────────────────────────────────────────────────────────── */
.section-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.67rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #8f9bb0;
  margin: 1.2rem 0 0.75rem 0;
  padding: 0 0 0.45rem 0.05rem;
  border-bottom: 1px solid #253247;
}

/* ── chart card ─────────────────────────────────────────────────────────────── */
.chart-card {
  background: #121821;
  border: 1px solid #253247;
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.chart-card:hover {
  border-color: #3a4d69;
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.35);
  transform: translateY(-1px);
}
.chart-card-preview {
  height: 96px;
  width: 100%;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  filter: saturate(0.55) brightness(0.85);
  border-bottom: 1px solid #253247;
}
.chart-card-preview::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(10,13,18,0.08) 0%, rgba(10,13,18,0.58) 100%),
    repeating-linear-gradient(
      0deg,
      rgba(255,255,255,0.03) 0px,
      rgba(255,255,255,0.03) 1px,
      transparent 1px,
      transparent 7px
    );
}
.chart-card-body {
  padding: 0.95rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  flex: 1;
}
.chart-card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.45rem;
}
.chart-card-category {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.56rem;
  font-weight: 500;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  margin-bottom: 0;
}
.chart-card-category.cat-crypto { color: #f0b90b; }
.chart-card-category.cat-macro  { color: #60a5fa; }
.chart-card-category.cat-tradfi { color: #a78bfa; }
.chart-card-state {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.55rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 0.18rem 0.42rem;
  border: 1px solid #31455f;
  color: #9fb2cb;
  background: rgba(49, 69, 95, 0.22);
}
.chart-card-state.live {
  border-color: rgba(19, 185, 129, 0.4);
  color: #95e7c5;
  background: rgba(19, 185, 129, 0.14);
}
.chart-card-name {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.96rem;
  font-weight: 600;
  color: #e7edf7;
  line-height: 1.3;
  margin-bottom: 0.42rem;
}
.chart-card-desc {
  font-size: 0.79rem;
  color: #8c9ab0;
  line-height: 1.45;
  flex: 1;
  min-height: 2.9rem;
  margin-bottom: 0.7rem;
}
.chart-card-meta {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.6rem;
}
.chart-card-chip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.55rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 0.16rem 0.38rem;
  border-radius: 5px;
  color: #95a7c1;
  background: rgba(24, 34, 49, 0.9);
  border: 1px solid #2a3a53;
}
.chart-card-fav {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.55rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #f0b90b;
  margin-bottom: 0.55rem;
}

/* ── override Open chart button inside chart card ───────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chart-card) .stButton > button,
.stButton > button.open-chart-btn {
  width: 100% !important;
  background: #182231 !important;
  border: 1px solid #2d3d57 !important;
  color: #dce5f2 !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  border-radius: 7px !important;
  padding: 0.48rem 0.9rem !important;
  transition: all 0.12s !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chart-card) .stButton > button:hover {
  background: #203048 !important;
  border-color: #3a5377 !important;
}

/* ── main area buttons ──────────────────────────────────────────────────────── */
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
  transition: all 0.12s !important;
}
.stButton > button:hover {
  background: #232b3e !important;
  border-color: #2d3a52 !important;
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

/* ── main form inputs ────────────────────────────────────────────────────────── */
div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label {
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.65rem !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: #848e9c !important;
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

/* ── alerts ─────────────────────────────────────────────────────────────────── */
div[data-testid="stAlert"] {
  border-radius: 6px !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.75rem !important;
}

/* ── dataframe ──────────────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] > div {
  border-radius: 6px !important;
  border: 1px solid #232b3e !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 0.78rem !important;
}

/* ── favourite star button ──────────────────────────────────────────────────── */
.fav-btn-wrap .stButton > button {
  background: transparent !important;
  border: 1px solid rgba(240,185,11,0.3) !important;
  color: #f0b90b !important;
  width: 2.2rem !important;
  height: 2.2rem !important;
  padding: 0 !important;
  font-size: 0.9rem !important;
  border-radius: 6px !important;
}
.fav-btn-wrap .stButton > button:hover {
  background: rgba(240,185,11,0.08) !important;
  border-color: #f0b90b !important;
}

/* ── chart detail description box ───────────────────────────────────────────── */
.chart-desc-box {
  background: #131722;
  border: 1px solid #232b3e;
  border-radius: 8px;
  padding: 1rem 1.2rem;
  margin-bottom: 1.25rem;
}
.chart-desc-box h4 {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: #eaecef;
  margin: 0 0 0.5rem 0;
}
.chart-desc-box p {
  font-size: 0.8rem;
  color: #848e9c;
  line-height: 1.6;
  margin: 0;
}
hr { border: none; border-top: 1px solid #232b3e !important; margin: 1rem 0 !important; }
</style>
"""


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _category_class(cat: str) -> str:
    return {
        "Crypto": "cat-crypto",
        "Macro":  "cat-macro",
        "TradFi": "cat-tradfi",
    }.get(cat, "cat-macro")


def _toggle_favourite(db, user_email, chart_name, key_suffix):
    if not user_email:
        st.button("☆", key=f"fav_{key_suffix}", disabled=True, help="Log in to save favourites")
        return False
    is_fav = chart_name in get_user_favourites(db, user_email)
    label   = "★" if is_fav else "☆"
    clicked = st.button(label, key=f"fav_{key_suffix}", help="Toggle favourite")
    if clicked:
        is_fav = toggle_user_favourite(db, user_email, chart_name)
    return is_fav


def _filter_chart_defs(
    chart_defs, category_choice, quick_choice, fav_choice,
    asset_choice, search_term, favourites, active_user,
):
    out = list(chart_defs)
    if category_choice != "All":
        out = [c for c in out if c.get("category") == category_choice]
    if quick_choice != "All":
        out = [c for c in out if quick_choice in c.get("quick", [])]
    if fav_choice == "Favourites":
        out = [c for c in out if c["name"] in favourites] if active_user else []
    if asset_choice != "All":
        out = [c for c in out if c.get("category") == "Crypto" and asset_choice in c.get("assets", [])]
    if search_term:
        out = [c for c in out if search_term in c["name"].lower()]
    return out


# ─── Dashboard grid ────────────────────────────────────────────────────────────

def _render_charts_dashboard(filtered_defs: list, favourites: set) -> None:
    st.markdown(
        '<div class="page-title">Charts Workspace</div>'
        '<div class="page-sub">Institutional-style chart library for macro and crypto research.</div>',
        unsafe_allow_html=True,
    )

    if not filtered_defs:
        st.info("No charts match the current filters.")
        return

    # Group by category
    grouped: dict[str, list] = {}
    for chart in filtered_defs:
        grouped.setdefault(chart.get("category", "Charts"), []).append(chart)

    for category, charts in grouped.items():
        cat_cls = _category_class(category)

        st.markdown(
            f'<div class="section-label">{category} Charts</div>',
            unsafe_allow_html=True,
        )

        # Rows of 3
        for row_start in range(0, len(charts), 3):
            row = charts[row_start: row_start + 3]
            cols = st.columns(3, gap="medium")
            for col, chart in zip(cols, row):
                with col:
                    preview_style = chart.get(
                        "preview",
                        "background: linear-gradient(140deg, #1a2035, #131722);"
                    )
                    is_fav = chart["name"] in favourites
                    is_live = chart.get("renderer") is not None
                    quick = ", ".join(chart.get("quick", [])[:2]) if chart.get("quick") else "General"
                    assets = ", ".join(chart.get("assets", [])[:2]) if chart.get("assets") else "All"
                    state_label = "Live" if is_live else "Soon"
                    state_cls = "live" if is_live else "soon"

                    with st.container(border=False):
                        st.markdown(
                            f"""
                            <div class="chart-card">
                              <div class="chart-card-preview" style="{preview_style}"></div>
                              <div class="chart-card-body">
                                <div class="chart-card-topline">
                                  <div class="chart-card-category {cat_cls}">{category}</div>
                                  <div class="chart-card-state {state_cls}">{state_label}</div>
                                </div>
                                <div class="chart-card-name">{chart['name']}</div>
                                <div class="chart-card-desc">{chart.get('summary', '')}</div>
                                <div class="chart-card-meta">
                                  <div class="chart-card-chip">Focus: {quick}</div>
                                  <div class="chart-card-chip">Assets: {assets}</div>
                                </div>
                                {"<div class='chart-card-fav'>★ Saved</div>" if is_fav else ""}
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "Open Chart",
                            key=f"open_{chart['slug']}",
                            use_container_width=True,
                        ):
                            st.session_state.charts_nav  = chart["name"]
                            st.session_state.charts_view = "detail"
                            st.rerun()


# ─── Main render ───────────────────────────────────────────────────────────────

def render_charts(db=None):
    load_dotenv()
    api_key = os.getenv("FRED_API_KEY") or st.secrets.get("FRED_API_KEY", "")
    if not api_key:
        st.error("FRED_API_KEY is missing. Add it to your .env or Streamlit secrets.")
        return

    st.markdown(_CSS, unsafe_allow_html=True)

    active_user = st.session_state.get("auth_user")

    # ── Session state init ──
    if "charts_nav" not in st.session_state:
        st.session_state.charts_nav = "Treasury Yield Curve"
    if "charts_view" not in st.session_state:
        st.session_state.charts_view = "dashboard"
    if not st.session_state.get("charts_initialized"):
        st.session_state.charts_view        = "dashboard"
        st.session_state.charts_initialized = True
        st.session_state.charts_category    = "All"
        st.session_state.charts_quick       = "All"
        st.session_state.charts_fav         = "All"
        st.session_state.charts_asset       = "All"
        st.session_state.charts_search      = ""

    # ── Sidebar ──
    category_options = ["All", "Crypto", "Macro", "TradFi"]
    quick_options    = ["All", "Rates", "Inflation", "Growth"]
    fav_options      = ["All", "Favourites"]
    asset_options    = ["All", "BTC", "ETH", "SOL"]

    with st.sidebar:
        st.subheader("Charts")
        st.caption("Workspace filters")

        category_choice = st.selectbox(
            "Category",
            options=category_options,
            index=category_options.index(st.session_state.get("charts_category", "All")),
            key="charts_category",
        )
        quick_choice = st.selectbox(
            "Quick Filter",
            options=quick_options,
            index=quick_options.index(st.session_state.get("charts_quick", "All")),
            key="charts_quick",
        )
        fav_choice = st.selectbox(
            "Favourites",
            options=fav_options,
            index=fav_options.index(st.session_state.get("charts_fav", "All")),
            key="charts_fav",
        )
        asset_choice = st.selectbox(
            "Asset",
            options=asset_options,
            index=asset_options.index(st.session_state.get("charts_asset", "All")),
            key="charts_asset",
        )
        search_input = st.text_input(
            "Search",
            placeholder="Search charts…",
            key="charts_search",
        )
        search_term = (search_input or "").strip().lower()

        st.divider()

        favourites = get_user_favourites(db, active_user) if active_user else set()

        filtered_defs = _filter_chart_defs(
            CHARTS,
            category_choice, quick_choice, fav_choice,
            asset_choice, search_term,
            favourites, active_user,
        )
        st.caption(f"{len(filtered_defs)} chart(s)")

        if fav_choice == "Favourites" and not active_user:
            st.caption("Log in to view saved charts.")

        flat_names = [c["name"] for c in filtered_defs]
        if not flat_names:
            st.caption("No charts match your filters.")
            selected_nav = st.session_state.charts_nav
        else:
            default_idx = 0
            if st.session_state.charts_nav in flat_names:
                default_idx = flat_names.index(st.session_state.charts_nav)
            selected_nav = st.radio(
                "Charts",
                options=flat_names,
                index=default_idx,
                label_visibility="collapsed",
            )

        if selected_nav != st.session_state.charts_nav:
            st.session_state.charts_nav  = selected_nav
            st.session_state.charts_view = "detail"

    # ── Main area ──
    with st.container():

        # ── Dashboard grid ──
        if st.session_state.charts_view != "detail":
            _render_charts_dashboard(filtered_defs, favourites)
            return

        # ── Back button ──
        if st.button("← Back to Charts", key="charts_back"):
            st.session_state.charts_view = "dashboard"
            st.rerun()

        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

        # ── Chart detail ──
        chart_map      = get_chart_map()
        selected_chart = chart_map.get(st.session_state.charts_nav)

        if not selected_chart:
            st.info("Chart not found.")
            return

        renderer = selected_chart.get("renderer")
        if not renderer:
            # Coming-soon placeholder
            st.markdown(
                f"""
                <div class="chart-desc-box">
                  <h4>{selected_chart['name']}</h4>
                  <p>{selected_chart.get('summary', '')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.info("This chart is coming soon.")
            return

        # Render with context (preserves all existing chart renderers)
        context = {
            "api_key": api_key,
            "favourites": favourites,
            "toggle_favourite": lambda name, suffix: _toggle_favourite(
                db, active_user, name, suffix
            ),
        }
        renderer(context)
