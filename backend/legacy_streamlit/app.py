import streamlit as st
from streamlit_navigation_bar import st_navbar

from tracker.db import get_db
from tracker.ui.dashboard import render_dashboard
from tracker.ui.journal import render_journal
from tracker.ui.charts import render_charts
from tracker.ui.auth import render_auth_dialog


def main():
    st.set_page_config(
        page_title="Trading Performance Tracker",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    routes = {
        "Dashboard": render_dashboard,
        "Journal":   render_journal,
        "Charts":    render_charts,
    }
    profile_page = "👤"
    pages = list(routes.keys()) + [profile_page]

    # ── Nav state ──
    if "nav_choice" not in st.session_state:
        st.session_state.nav_choice = "Dashboard"
    if "nav_key" not in st.session_state:
        st.session_state.nav_key     = "main_nav_0"
        st.session_state.nav_counter = 0
    if st.session_state.get("nav_reset"):
        st.session_state.nav_counter += 1
        st.session_state.nav_key   = f"main_nav_{st.session_state.nav_counter}"
        st.session_state.nav_reset = False

    # ── Navigation bar ──
    # Styled to match the IBM Plex / TradingView-dark design system
    choice = st_navbar(
        pages,
        selected=st.session_state.nav_choice,
        styles={
            "nav": {
                "background-color":  "#0d1117",
                "border-bottom":     "1px solid #232b3e",
                "height":            "52px",
                "padding":           "0 2rem",
                "font-family":       "'IBM Plex Sans', sans-serif",
            },
            "span": {
                "color":          "#848e9c",
                "font-weight":    "500",
                "font-size":      "0.82rem",
                "letter-spacing": "0.02em",
                "font-family":    "'IBM Plex Sans', sans-serif",
            },
            "active": {
                "color":       "#eaecef",
                "font-weight": "600",
            },
            "hover": {
                "color":            "#eaecef",
                "background-color": "rgba(255,255,255,0.04)",
            },
        },
        adjust=False,
        key=st.session_state.nav_key,
    )

    if choice != "Charts":
        st.session_state.charts_initialized = False

    # ── Global CSS ──
    # Unified design system: IBM Plex Sans/Mono, TradingView × Binance dark.
    # Minimal overrides only — page-level CSS lives in each render function.
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

        /* ── tokens ──────────────────────────────────────────────────────────── */
        :root {
          --bg:       #0b0e17;
          --surface:  #131722;
          --elevated: #1a2035;
          --border:   #232b3e;
          --border2:  #2d3a52;
          --text:     #eaecef;
          --text2:    #848e9c;
          --text3:    #4a5568;
          --pos:      #0ecb81;
          --neg:      #f6465d;
          --gold:     #f0b90b;
          --blue:     #1677ff;
          --nav-h:    52px;
        }

        /* ── base ────────────────────────────────────────────────────────────── */
        *, *::before, *::after { box-sizing: border-box; }

        html, body, [class*="css"] {
          font-family: 'IBM Plex Sans', sans-serif;
          -webkit-font-smoothing: antialiased;
        }

        html, body, .stApp {
          background: var(--bg);
          color: var(--text);
        }

        div[data-testid="stAppViewContainer"] { background: transparent; }

        section.main { background: transparent; }

        .block-container {
          padding-top: 1.5rem;
          padding-bottom: 4rem;
          max-width: 1480px;
        }

        /* ── typography ──────────────────────────────────────────────────────── */
        h1, h2, h3, h4, h5, h6 {
          font-family: 'IBM Plex Sans', sans-serif;
          letter-spacing: -0.01em;
          font-weight: 600;
          color: var(--text);
        }

        /* ── scrollbar ───────────────────────────────────────────────────────── */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--border2); }

        /* ── hide streamlit chrome ───────────────────────────────────────────── */
        header[data-testid="stHeader"] { display: none !important; }
        footer                         { display: none !important; }
        #MainMenu                      { display: none !important; }
        .stDeployButton                { display: none !important; }
        div[data-testid="stToolbar"]   { display: none !important; }
        #stDecoration                  { display: none !important; }

        /* ── nav bar iframe (streamlit_navigation_bar) ───────────────────────── */
        iframe[title="streamlit_navigation_bar.st_navbar"] {
          position: fixed;
          top: 0; left: 0; right: 0;
          width: 100%;
          height: var(--nav-h);
          border: none;
          z-index: 10000;
          box-shadow: 0 1px 0 var(--border);
        }

        section.main,
        div[data-testid="stAppViewContainer"] > section {
          padding-top: calc(var(--nav-h) + 0px) !important;
        }

        /* ── sidebar ─────────────────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {
          background: #0d1117 !important;
          border-right: 1px solid var(--border) !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] {
          width: 2.8rem !important;
          min-width: 2.8rem !important;
          max-width: 2.8rem !important;
          overflow: visible !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {
          opacity: 0 !important;
        }
        div[data-testid="collapsedControl"] {
          display: block !important;
          visibility: visible !important;
          opacity: 1 !important;
          pointer-events: auto !important;
        }

        /* ── containers / cards ──────────────────────────────────────────────── */
        div[data-testid="stVerticalBlockBorderWrapper"] {
          background: var(--surface);
          border: 1px solid var(--border) !important;
          border-radius: 8px !important;
          box-shadow: none !important;
        }

        /* ── inputs (global fallback — per-page CSS takes priority) ──────────── */
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-baseweb="select"] > div {
          background: var(--elevated) !important;
          border: 1px solid var(--border) !important;
          border-radius: 6px !important;
          color: var(--text) !important;
          font-family: 'IBM Plex Mono', monospace !important;
        }
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea {
          color: var(--text) !important;
          font-family: 'IBM Plex Mono', monospace !important;
        }
        div[data-baseweb="select"] [role="listbox"] {
          background: var(--elevated) !important;
          color: var(--text) !important;
          border-radius: 6px;
          border: 1px solid var(--border) !important;
        }

        /* ── buttons (global fallback) ───────────────────────────────────────── */
        .stButton > button {
          font-family: 'IBM Plex Sans', sans-serif !important;
          font-size: 0.78rem !important;
          font-weight: 500 !important;
          background: var(--elevated) !important;
          border: 1px solid var(--border) !important;
          color: var(--text) !important;
          border-radius: 6px !important;
          padding: 0.45rem 1rem !important;
          height: auto !important;
          transition: all 0.12s ease !important;
        }
        .stButton > button:hover {
          background: var(--border) !important;
          border-color: var(--border2) !important;
        }
        .stButton > button[kind="primary"] {
          background: var(--pos) !important;
          border-color: var(--pos) !important;
          color: var(--bg) !important;
          font-weight: 600 !important;
        }
        .stButton > button[kind="primary"]:hover {
          background: #0bb872 !important;
          border-color: #0bb872 !important;
          color: var(--bg) !important;
        }

        /* ── dataframe ───────────────────────────────────────────────────────── */
        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] > div {
          border-radius: 6px !important;
          border: 1px solid var(--border) !important;
          font-family: 'IBM Plex Mono', monospace !important;
          font-size: 0.78rem !important;
        }

        /* ── alerts ──────────────────────────────────────────────────────────── */
        div[data-testid="stAlert"] {
          border-radius: 6px !important;
          font-family: 'IBM Plex Mono', monospace !important;
          font-size: 0.75rem !important;
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

        /* ── misc ────────────────────────────────────────────────────────────── */
        hr { border: none; border-top: 1px solid var(--border) !important; }
        a  { color: var(--blue); }
        .stCaption, .stCaption p {
          font-family: 'IBM Plex Mono', monospace !important;
          color: var(--text3) !important;
          font-size: 0.72rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Route ──
    if choice == profile_page:
        st.session_state.show_auth_dialog = True
        st.session_state.nav_reset        = True
        st.rerun()
        choice = st.session_state.nav_choice
    else:
        st.session_state.nav_choice = choice

    db = get_db()
    render_auth_dialog(db)
    routes.get(choice, render_dashboard)(db)


if __name__ == "__main__":
    main()