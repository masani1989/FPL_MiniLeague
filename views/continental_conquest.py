import pandas as pd
import streamlit as st

import Utils.gameweek as gwk
import Utils.supabase_conn as db
from Utils import config

# ---------------------------------------------------------------------------
# Styling — mirror views/last_man_standing.py for a consistent look across pages.
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
    f'>Continental Conquest</h1>',
    unsafe_allow_html=True,
)
st.divider()

# Contest context
contest = db.load_cc_contest()
season_id = config.SEASON_ID

tab_groups, tab_fixtures, tab_bracket = st.tabs(["Groups", "Fixtures", "Bracket"])

# ---------------------------------------------------------------------------
# Groups — two standings tables (A & B), qualification color-coded.
# ---------------------------------------------------------------------------
with tab_groups:
    st.subheader("Group Stage", anchor=False)

    if contest is None:
        st.info("No Continental Conquest contest has been set up for this season yet.")
    else:
        status = contest.get("status", "setup")
        phase = contest.get("phase", "league")
        current_gw = contest.get("current_gw")
        st.caption(f"Contest status: **{status}**   |   Phase: **{phase}**   |   Current GW: **{current_gw}**")

        standings = db.load_cc_standings(season_id)
        if standings.empty:
            st.write("No group standings available yet.")
        else:
            _QUAL_COLORS = {
                "ucl": "#1b9e3e",       # green — UCL qualification
                "uel": "#e0a800",       # amber — UEL qualification
                "eliminated": "#888888",  # grey — out
            }
            for group_name in sorted(standings["Group"].dropna().unique()):
                st.markdown(f"#### Group {group_name}")
                gdf = standings[standings["Group"] == group_name].reset_index(drop=True)
                styled = gdf.style.apply(
                    lambda row: [
                        f"color: {_QUAL_COLORS.get(row['Qualification'], '#222')}; font-weight: bold"
                        if col == "Qualification" else "" for col in gdf.columns
                    ],
                    axis=1,
                )
                st.dataframe(styled, use_container_width=True, hide_index=True)
                q = gdf["Qualification"].value_counts()
                st.caption(
                    " / ".join(f"{k.upper()}: {v}" for k, v in q.items() if k)
                )


# ---------------------------------------------------------------------------
# Fixtures — gameweek selector -> that GW's matches with scores.
# ---------------------------------------------------------------------------
with tab_fixtures:
    st.subheader("Fixtures", anchor=False)

    if contest is None:
        st.info("No Continental Conquest contest has been set up for this season yet.")
    else:
        finished_gws = []

        try:
            events = gwk.get_gameweek_data()["events"]
            finished_gws = sorted([e["id"] for e in events])[:26]# if e.get("finished")])
        except Exception:
            finished_gws = []

        if not finished_gws:
            st.write("No finished gameweeks available yet.")
        else:
            default_gw = st.session_state.get("gw_id", finished_gws[-1])
            if default_gw not in finished_gws:
                default_gw = finished_gws[-1]
            selected_gw = st.selectbox(
                "Matchday",
                options=["All"] + [str(gw) for gw in finished_gws],
                index=finished_gws.index(default_gw)
            )

            fixtures = db.load_cc_fixtures(season_id, int(selected_gw) if selected_gw != "All" else None)
            if fixtures.empty:
                st.write(f"No Continental Conquest fixtures for Gameweek {selected_gw}.")
            else:
                fixture_groups = sorted(fixtures["Group"].dropna().unique())
                selected_group = st.selectbox(
                    "Group",
                    options=["All"] + fixture_groups,
                    index=0,
                )

                # dropdown filter for players
                players = sorted(fixtures["Home"].dropna().unique()) if selected_group == "All" else sorted(fixtures[fixtures["Group"] == selected_group]["Home"].dropna().unique())
                selected_player = st.selectbox(
                    "Player",
                    options=["All"] + players,
                    index=0,
                )

                display_fixtures = (
                    fixtures if selected_group == "All"
                    else fixtures[fixtures["Group"] == selected_group].reset_index(drop=True)
                )

                final_fixtures = (display_fixtures if selected_player == "All" 
                                  else display_fixtures[(display_fixtures["Home"] == selected_player) 
                                                        | (display_fixtures["Away"] == selected_player)]).sort_values(by=["Round"], key=lambda col: col.str.extract(r"(\d+)")[0].astype(int)).reset_index(drop=True)

                st.dataframe(final_fixtures, use_container_width=True, hide_index=True)
                played = (final_fixtures["Result"] != "-").sum()
                total = len(final_fixtures)
                st.caption(f"Showing **{total}** matches | Played: **{played}** / {total}")


# ---------------------------------------------------------------------------
# Bracket — UCL + UEL ties per round with winners.
# ---------------------------------------------------------------------------
with tab_bracket:
    st.subheader("Knockout Bracket", anchor=False)

    if contest is None:
        st.info("No Continental Conquest contest has been set up for this season yet.")
    else:
        ties = db.load_cc_ties(season_id)
        if ties.empty:
            st.write("No knockout ties drawn yet. The bracket is built after the group stage.")
        else:
            for competition in sorted(ties["Competition"].unique()):
                label = "Champions League" if competition == "ucl" else "Europa League"
                st.markdown(f"#### {label}")
                cdf = ties[ties["Competition"] == competition]
                st.dataframe(cdf, use_container_width=True, hide_index=True)