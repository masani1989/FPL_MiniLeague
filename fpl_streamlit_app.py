import streamlit as st
from pathlib import Path
import Utils.gameweek as gwk

st.set_page_config(layout="wide")

global deadline, later_gw, completed_months

deadline = gwk.get_upcoming_deadline()
latest_gw = gwk.get_recent_completed_gameweek()
completed_months = list(gwk.get_till_latest_phase().keys()) if gwk.get_till_latest_phase() else ['0']

st.session_state['gw_id'] = latest_gw[0]
st.session_state['gw_status'] = latest_gw[1]
st.session_state['completed_months'] = completed_months
st.session_state['deadline'] = deadline

# --- CUSTOM CSS INJECTION ---
with open("assets/custom_sidebar.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- PAGE SETUP ---
about_page = st.Page(
    'views/about_me.py',
    title='Get Started',
    icon=':material/info:',
    default=True,
)
league = st.Page(
    'views/minileague.py',
    title='League Statistics',
    icon=':material/emoji_events:',
)
analytics = st.Page(
    'views/analytics.py',
    title='Manager Statistics',
    icon=':material/analytics:'
)
myspace = st.Page(
    'views/myspace.py',
    title='My Space',
    icon=':material/groups:',
)

# --- NAVIGATION SETUP [WITH SECTIONS]---
pg = st.navigation(
    {
        "Welcome": [about_page],
        "Menu": [league, analytics, myspace],
    }
)

# --- SHARED ON ALL PAGES ---
st.logo("assets/fpl.png")

# --- RUN NAVIGATION ---
pg.run()
