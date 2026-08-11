from datetime import datetime, timedelta
import Utils.refreshData as rd
import streamlit as st
from Utils.league import *
import Utils.supabase_conn as db
# from fpl_streamlit_app import deadline, latest_gw

st.markdown(f'<h1 style="color:#33ff33;font-size:60px;background-image:linear-gradient(45deg, #1A512E, #63A91F);font-family:Montserrat;text-align:left;padding:20px;border-radius:10px;"'
            f'>Fantasy Kings 2025-26</h1>', unsafe_allow_html=True)

# CSS styles for various elements on the screen
st.html(
    '''
    <style>
    hr {
        border-color: yellow;
    }
    </style>
    '''
)

st.markdown("""
<style>
.big-font {
    font-size:20px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.st-emotion-cache-sesqrs {
    font-size:18px;
    color: yellow;
}
</style>
""", unsafe_allow_html=True)

st.divider()

dataDate = db.load_data_date()
gw_state = str(st.session_state['gw_id']) + ' ' + {st.session_state['gw_status'] == False: 'In-Progress', st.session_state['gw_status'] == True: 'Complete'}.get(True)

# Custom visual block for Gameweek info
st.markdown(f"""
<div style='background: #333; border-radius: 12px; padding: 18px 24px; margin-bottom: 10px; display: flex; align-items: center;'>
    <img src='https://img.icons8.com/color/48/football2.png' style='width:40px;height:40px;margin-right:18px;' alt='GW'/>
    <div>
        <span style='font-size:22px; color:#FFD700; font-weight:600;'>Gameweek {gw_state}</span><br>
        <span style='font-size:15px; color:#FFD700;'>Last Data Refresh: <b style='color:#fff;'>{datetime.strptime(dataDate.loc[0, ['DataAsOf']].to_string(index=False), '%m/%d/%Y %H:%M:%S')}</b></span>
    </div>
</div>
<div style='background: #333; border-radius: 12px; padding: 14px 24px; margin-bottom: 18px; display: flex; align-items: center;'>
    <img src='https://img.icons8.com/color/48/alarm.png' style='width:40px;height:40px;margin-right:18px;' alt='Deadline'/>
    <span style='font-size:22px; color:#FFD700; font-weight:600;'>Gameweek {str(st.session_state['gw_id']+1)} <b>Deadline</b>: <span style='color:#fff;'>{st.session_state['deadline']}</span></span>
</div>
""", unsafe_allow_html=True)


st.write('\n')

is_clicked = st.button('Refresh Data')
if is_clicked:
    with st.spinner('In-Progress......'):
        st.cache_data.clear()
        rd.refGw()
        db.log_data_refresh(status="success", notes="Manual refresh via UI")

st.divider()

st.write('\n')

_help = st.container(border=True)

# Usage Guidelines
with _help:
    st.markdown(
        """
        :green[**Usage Guidelines:**]
           - :grey[Check the Data as of notification above ☝️. If you feel the gameweek information would have been 
           updated since the date displayed, Click on 'Refresh Data' button]
           - :blue[Wait for the In-Progress spinner to disappear and do not click anywhere on the screen. It takes some 
           time to pull data from FPL servers. Once complete, 
           you will notice that Data as of is updated and it also gives the latest state of current gameweek]
           - :grey[Do not click on the refresh data button if the information is latest on the basis of data as of value]
           - :grey[Once refreshed, the app is good to use]
        
        :green[**League Statistics:**]
           - :grey[Click on this option in the sidebar navigation pane, to get information on various leaderboards and 
           winnings till date]
           - :grey[First table shows **Overall Standings**. Click in the first column (before Rank) against any 
           player in this table to get Weekly and Monthly winnings for that player]
           - :grey[The next two tables are for Gameweek and Monthly rankings. Use the slider option to choose 
           any GW and Month]
           - :grey[The last table on this page is for Total Winnings per player till date]
           
        :green[**Manager Statistics:**]
           - :grey[Click on this option in the sidebar navigation pane, to get information on manager performances 
           and analytic measures]
           - :grey[There are two sections]
             - :grey[Comparison Trends: You can choose multiple players from the dropdown box to check historical 
             year's ranks and Current Year's Rank Progression by passing gameweek]
             - :grey[Player Performance: This graph can be checked for one player at a time and gives information about 
              each gameweek's rank and points earned]
        """, unsafe_allow_html=True)

lg = league(581588)
lg_name = lg.get_league_name()

st.divider()

st.write('Support')
col1, col2 = st.columns([0.3, 4], gap="small", vertical_alignment="center")
with col1:
    st.image("./assets/profile_image.png", width=80)

with col2:
    st.caption("Himanshu Masani")
    st.caption('FPL Admin for Fantasy Kings 2024-25')
    if st.button("✉️ Contact Me"):
        st.warning('''
                - Phone : xxxxx
                - Email : test@test.com
                ''')
