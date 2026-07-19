import streamlit as st

from auth import login
from config import APP_NAME, APP_VERSION
from depot import render_depot
from planning import render_planning

st.set_page_config(page_title=APP_NAME, layout="wide")

role = login()

if role == "tedarik":
    render_planning()
elif role == "depo":
    render_depot()

st.sidebar.caption(f"{APP_NAME} · v{APP_VERSION}")
