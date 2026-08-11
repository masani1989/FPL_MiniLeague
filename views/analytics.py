import time
import matplotlib.pyplot as plt
import streamlit as st
from Utils.league import *
import plyr_history as ph
import pandas as pd
from streamlit import session_state as session_state
import Utils.supabase_conn as db
import altair as alt

lg = league(581588)

st.markdown('<h1 style="color:#33ff33;font-size:60px;background-image:linear-gradient(45deg, #1A512E, #63A91F);font-family:Montserrat;text-align:left;padding:20px;border-radius:10px;"'
            '>Manager Performance - Analysis</h1>', unsafe_allow_html=True)
st.divider()

plyrs = lg.get_league_players()
plr_entry_link = [{p['Player']: p['Id']} for p in plyrs]
plyr_lst = pd.DataFrame.from_records(plyrs).get('Player')

# Get gameweek data from Supabase
gw_data = db.load_gameweek()[['Player', 'Points', 'Gameweek']] \
    .astype({'Points': 'int64', 'Gameweek': 'int64'})

gw_data['Players'] = [x.split(' ')[0].capitalize() + ' ' + x.split(' ')[1].capitalize() for x in gw_data['Player']]

# Build dataframe with cumulative points by gameweek for each manager and subsequent ranking
gw_data_cum = gw_data.groupby(['Player', 'Players', 'Gameweek']).sum().groupby(level=0).cumsum()
gw_data_cum['Rank'] = gw_data_cum.groupby(['Gameweek'])['Points'].rank(method='dense', ascending=False)

if 'button_sent' not in session_state:
    session_state['button_sent'] = True

_container1 = st.container(border=True)

with _container1:
    st.markdown('<h2 style="color:yellow;font-size:40px;">Comparison Trends</h2>', unsafe_allow_html=True)
    st.write('\n')

    # Select players for comparison charts section
    option = st.multiselect(label='Select Players', options=plyr_lst,  # on_change=button_state_change(),
                            placeholder="Choose Player(s)", label_visibility='collapsed', default=[plyr_lst[0], plyr_lst[1]])
    gw_data_option = gw_data_cum.query(f'Players in {option}').reset_index()

    col1, col2 = st.columns(2)

    # Global Rank Chart section
    with col1:
        st.write('\n')
        st.subheader("**Global Rank - Historical**\n", anchor=False)
        st.write('\n')
        if session_state['button_sent']:
            if option is None:
                option = ''
            else:
                data = ph.plyr_hist([p[i] for i in option for p in plr_entry_link if i in p], plr_entry_link)
                st.bar_chart(data, x="Season", y="Rank", color='Player Name', stack=False)

    # Rank Progress Chart section
    with col2:
        st.write('\n')
        st.subheader("**Rank Progression - Current Season**\n", anchor=False)

        if session_state['button_sent'] and option is not None:
            chart1 = alt.Chart(gw_data_option).mark_line(point=True).encode(
                x=alt.X('Gameweek', scale=alt.Scale(reverse=False, domain=[0, 38]), axis=alt.Axis(grid=False)),
                y=alt.Y('Rank', scale=alt.Scale(reverse=True, domain=[1, 21]), axis=alt.Axis(grid=True, tickCount=9)),
                color=alt.Color("Players", legend=alt.Legend(orient='bottom'))
            ).properties(
                width=580,
                height=350
            )

            st.altair_chart(chart1, use_container_width=True)

    st.divider()

    st.markdown('<h2 style="color:yellow;font-size:40px;">Player Performance - Gameweek</h2>', unsafe_allow_html=True)
    st.write('\n')

    # Select player for gameweek performance chart
    option1 = st.selectbox(label='Select Players', options=plyr_lst,
                           placeholder="Choose Player", label_visibility='collapsed')

    # Gameweek Performance Chart section
    if option1 is not None:
        gw_data_plr = gw_data
        gw_data_plr['Rank'] = gw_data_plr.groupby(['Gameweek'])['Points'].rank(method='dense', ascending=False)
        gw_data_plr_filtered = gw_data.query(f"Players == '{option1}'").reset_index().sort_values('Gameweek')

        gw = gw_data_plr_filtered['Gameweek']
        rank = gw_data_plr_filtered['Rank']
        pts = gw_data_plr_filtered['Points']

        fig, ax1 = plt.subplots(figsize=(16, 5), facecolor=st.get_option('theme.backgroundColor'))

        ax1.plot(gw, rank, color='white', marker='*', linewidth=0.7, label='Rank', alpha=0.7) # '#002b36'
        ax1.set_xlabel('Gameweek', color='white')
        ax1.set_ylabel('Rank', color='white')
        ax1.tick_params(axis='y', labelcolor='white')
        ax1.tick_params(axis='x', labelcolor='white')
        # ax1.gca().invert_yaxis()
        ax1.set_ylim(0, 21)
        ax1.set_xlim(0, 39)
        ax1.invert_yaxis()
        ax1.axhspan(0, 21, facecolor=st.get_option('theme.backgroundColor'), alpha=0.9)

        # Create a twin axis
        ax2 = ax1.twinx()
        p = ax2.bar(gw, pts, color='#35cbe8', label='Points', alpha=0.5) # 0e8dad
        ax2.set_ylabel('Points', color='white')
        ax2.tick_params(axis='y', labelcolor='white')
        ax2.bar_label(p, label_type='center', color='yellow')

        plt.title(f'Player Performance - {option1}', color='white')
        st.pyplot(plt)
