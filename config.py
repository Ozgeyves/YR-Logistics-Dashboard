import streamlit as st
from config import APP_NAME


def _secret(name: str, fallback: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return fallback


def login() -> str:
    if "role" not in st.session_state:
        st.session_state["role"] = None

    if st.session_state["role"]:
        return st.session_state["role"]

    st.title(APP_NAME)
    st.caption("Giriş için şifrenizi yazın.")

    password = st.text_input("Şifre", type="password")

    if st.button("Giriş Yap", type="primary"):
        tedarik_password = _secret("TEDARIK_PASSWORD", "tedarik")
        depo_password = _secret("DEPO_PASSWORD", "depo")

        if password == tedarik_password:
            st.session_state["role"] = "tedarik"
            st.rerun()
        elif password == depo_password:
            st.session_state["role"] = "depo"
            st.rerun()
        else:
            st.error("Şifre hatalı.")

    st.stop()


def logout_button(key: str) -> None:
    if st.sidebar.button("Çıkış Yap", key=key):
        st.session_state["role"] = None
        st.rerun()
