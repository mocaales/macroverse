import json

import streamlit as st
import streamlit.components.v1 as components

from tracker.auth import (
    authenticate_user,
    create_session,
    get_session,
    get_user,
    invalidate_session,
    logout_user,
    register_user,
)


COOKIE_NAME = "tpt_session"
COOKIE_MAX_AGE_SECONDS = 3 * 60 * 60


def _get_query_token():
    try:
        token = st.query_params.get("session")
        if isinstance(token, list):
            token = token[0] if token else None
        return token
    except Exception:
        params = st.experimental_get_query_params()
        return params.get("session", [None])[0]


def _clear_query_token():
    try:
        if "session" in st.query_params:
            del st.query_params["session"]
    except Exception:
        st.experimental_set_query_params()


def _get_cookie_token():
    try:
        token = st.context.cookies.get(COOKIE_NAME)
        if isinstance(token, list):
            token = token[0] if token else None
        return token or None
    except Exception:
        return None


def _render_cookie_sync(token, clear=False):
    token_js = json.dumps(token or "")
    cookie_name_js = json.dumps(COOKIE_NAME)
    max_age_js = int(COOKIE_MAX_AGE_SECONDS)
    clear_js = "true" if clear else "false"
    html = f"""
    <script>
    (function() {{
      const key = {cookie_name_js};
      const token = {token_js};
      const maxAge = {max_age_js};
      const clear = {clear_js};
      let topWindow = null;
      try {{
        topWindow = window.parent;
        void topWindow.location.href;
      }} catch (err) {{
        topWindow = window;
      }}
      const secureFlag = topWindow.location.protocol === "https:" ? "; Secure" : "";

      if (clear) {{
        topWindow.document.cookie = key + "=; Max-Age=0; Path=/; SameSite=Lax" + secureFlag;
        return;
      }}

      if (token) {{
        topWindow.document.cookie =
          key + "=" + encodeURIComponent(token) +
          "; Max-Age=" + maxAge +
          "; Path=/; SameSite=Lax" + secureFlag;
      }}
    }})();</script>
    """
    components.html(html, height=0)


def _sync_auth_state(db):
    token = st.session_state.get("auth_token")
    if token:
        session = get_session(db, token)
        if session:
            st.session_state.auth_user = session.get("email")
            st.session_state.auth_token = token
            return token, False

        st.session_state.auth_user = None
        st.session_state.auth_token = None
        return "", True

    token = _get_cookie_token()
    if token:
        session = get_session(db, token)
        if session:
            st.session_state.auth_user = session.get("email")
            st.session_state.auth_token = token
            return token, False

        st.session_state.auth_user = None
        st.session_state.auth_token = None
        return "", True

    # Migration fallback from old query-param sessions.
    token = _get_query_token()
    if token:
        session = get_session(db, token)
        _clear_query_token()
        if session:
            st.session_state.auth_user = session.get("email")
            st.session_state.auth_token = token
            return token, False
        st.session_state.auth_user = None
        st.session_state.auth_token = None
        return "", True

    if st.session_state.get("auth_user") and not st.session_state.get("auth_token"):
        st.session_state.auth_user = None

    return "", False


def render_auth_dialog(db):
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None

    token, clear = _sync_auth_state(db)
    _render_cookie_sync(token, clear=clear)

    if not st.session_state.get("show_auth_dialog"):
        return

    st.session_state.show_auth_dialog = False

    @st.dialog("Account")
    def _auth_dialog():
        if st.session_state.auth_user:
            email = st.session_state.auth_user
            user = get_user(db, email) or {}
            status = "Active" if user.get("active") else "Inactive"
            st.markdown(f"**{email}**")
            st.markdown(f"Status: {status}")
            if st.button("Log out", key="auth_logout"):
                logout_user(db, email)
                invalidate_session(db, st.session_state.auth_token)
                st.session_state.auth_user = None
                st.session_state.auth_token = None
                _clear_query_token()
                _render_cookie_sync("", clear=True)
        else:
            mode = st.radio(
                "Auth mode",
                options=["Log in", "Register"],
                horizontal=True,
                label_visibility="collapsed",
                key="auth_mode",
            )
            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                confirm = None
                if mode == "Register":
                    confirm = st.text_input("Confirm password", type="password")
                submit_label = "Log in" if mode == "Log in" else "Create account"
                submitted = st.form_submit_button(submit_label)
            if submitted:
                if mode == "Log in":
                    ok, payload = authenticate_user(db, email, password)
                    if ok:
                        token = create_session(db, payload)
                        st.session_state.auth_user = payload
                        st.session_state.auth_token = token
                        _render_cookie_sync(token, clear=False)
                    else:
                        st.error(payload)
                else:
                    ok, msg = register_user(db, email, password, confirm)
                    if ok:
                        email_norm = email.strip().lower()
                        token = create_session(db, email_norm)
                        st.session_state.auth_user = email_norm
                        st.session_state.auth_token = token
                        _render_cookie_sync(token, clear=False)
                        st.success(msg)
                    else:
                        st.error(msg)

    _auth_dialog()
