import pandas as pd
import streamlit as st

import Utils.gameweek as gwk
import Utils.supabase_conn as db
from Utils import config

# ---------------------------------------------------------------------------
# Styling — mirror views/minileague.py for a consistent look across pages.
# ---------------------------------------------------------------------------
st.markdown("""
    <style>
    .stDataFrame, .stTable {
        border-radius: 18px !important;
        box-shadow: 0 6px 32px rgba(51,255,51,0.10), 0 1.5px 8px rgba(51,255,51,0.08);
        background: linear-gradient(90deg, #f8f7f3 0%, #ecebe4 80%, #e2e1d9 100%) !important;
        border: 2px solid #ecebe4 !important;
        margin-bottom: 18px;
        overflow: hidden;
    }
    .stDataFrame table { font-size: 1.08rem; border-radius: 12px; overflow: hidden; }
    .stDataFrame th {
        background: #33ff33 !important;
        color: #124010 !important;
        font-size: 1.18rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px;
        border-bottom: 2px solid #ecebe4 !important;
    }
    .stDataFrame td {
        background: rgba(245,245,240,0.12) !important;
        color: #222 !important;
        border-bottom: 1px solid #ecebe4 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 18px;
        background: rgba(71,155,41,0.15) !important;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(51,255,51,0.12), 0 2px 8px rgba(51,255,51,0.10);
        padding: 14px 0px;
        width: 100%;
        display: flex;
        justify-content: space-between;
        backdrop-filter: blur(12px);
        border: none;
    }
    .stTabs [data-baseweb="tab"] {
        height: 54px;
        color: #f3f3f3;
        background: linear-gradient(120deg, #9a9a9a 0%, #6f6f6f 100%);
        border-radius: 14px;
        font-weight: 600;
        margin: 0;
        padding: 0px 36px;
        border: 1px solid rgba(0,0,0,0.14);
        flex-grow: 1;
        text-align: center;
        font-size: 1.22rem;
        opacity: 0.92;
    }
    .stTabs [data-baseweb="tab"] button,
    .stTabs [data-baseweb="tab"] > button {
        background: transparent !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #33ff77 0%, #a8ffd0 40%, #eaffea 100%);
        color: #053212;
        font-weight: 800;
        font-size: 1.38rem;
        box-shadow: 0 12px 36px rgba(51,255,51,0.22), 0 0 0 3px rgba(51,255,51,0.08);
        border: 2.5px solid rgba(0,200,83,0.95);
        opacity: 1;
        transform: scale(1.09);
    }
    button:focus { outline: none !important; }
    </style>
    """, unsafe_allow_html=True)

# Page title
st.markdown(
    f'<h1 style="color:#33ff33;font-size:60px;background-image:linear-gradient(45deg, #1A512E, #63A91F);'
    f'font-family:Montserrat;text-align:left;padding:20px;border-radius:10px;"'
    f'>Last Man Standing</h1>',
    unsafe_allow_html=True,
)
st.divider()

# Contest context
contest = db.load_lms_contest()
season_id = config.SEASON_ID

tab_survivors, tab_gw = st.tabs(["Survivors", "Gameweek"])

with tab_survivors:
    st.subheader("Survivors", anchor=False)

    if contest is None:
        st.info("No Last Man Standing contest has been set up for this season yet.")
    else:
        status = contest.get("status", "active")
        current_gw = contest.get("current_gw")
        status_label = "Completed" if status == "completed" else "Active"
        st.caption(f"Contest status: **{status_label}**   |   Current GW: **{current_gw}**")

        standings = db.load_lms_standings(season_id)
        if standings.empty:
            st.write("No standings data available yet.")
        else:
            st.dataframe(standings, use_container_width=True, hide_index=True)
            alive_count = (standings["Status"] == "Alive").sum()
            st.caption(f"Alive: **{alive_count}** / {len(standings)} managers")

with tab_gw:
    st.subheader("Gameweek Scorecard", anchor=False)

    # Build the list of finished gameweeks from the FPL bootstrap events.
    finished_gws = []
    try:
        events = gwk.get_gameweek_data()["events"]
        finished_gws = sorted([e["id"] for e in events if e.get("finished")])
    except Exception:
        finished_gws = []

    if not finished_gws:
        st.write("No finished gameweeks available yet.")
    else:
        default_gw = st.session_state.get("gw_id", finished_gws[-1])
        if default_gw not in finished_gws:
            default_gw = finished_gws[-1]
        selected_gw = st.selectbox(
            "Select Gameweek",
            options=finished_gws,
            index=finished_gws.index(default_gw),
            label_visibility="collapsed",
        )

        scores = db.load_lms_gw_scores(season_id, selected_gw)
        if scores.empty:
            st.write(f"No scorecard data available for Gameweek {selected_gw}.")
        else:
            st.dataframe(scores, use_container_width=True, hide_index=True)
            eliminated = scores.loc[scores["Eliminated"] == "Yes", "Player"].tolist()
            if eliminated:
                st.error(f"Eliminated this gameweek: {', '.join(eliminated)}")
            else:
                st.caption("No eliminations this gameweek — everyone survived.")