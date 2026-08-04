import streamlit as st
import pandas as pd
import Utils.supabase_conn as db


@st.cache_data()
def data_refresh():
    """
    Function to refresh data from Supabase containing the GW, Monthly and Overall standings and points.
    :return: tuple of (ovr_data, gw_data, mn_data)
    """
    ovr_data = db.load_overall()
    gw_data = db.load_gameweek()
    mn_data = db.load_monthly()
    return ovr_data, gw_data, mn_data

@st.cache_data()
def winnings_data(gw_data, mn_data):
    """
    Function to calculate the winnings across the mini league
    :return: DataFrame of winnings data
    """

    #Calculatate the overall winnings
    gw_data = gw_data[(gw_data.Gameweek < st.session_state['gw_id']) | ((gw_data.Gameweek == st.session_state['gw_id']) & (st.session_state['gw_status']))]
    mn_data = mn_data[mn_data.Month.isin(st.session_state['completed_months'])]

    gw_data_rankers = gw_data[gw_data['Rank'] == 1].groupby(['Gameweek', 'Rank']).size().reset_index(name='Count').sort_values('Gameweek')
    mn_data_rankers = mn_data[mn_data['Rank'] == 1].groupby(['Month', 'Rank']).size().reset_index(name='Count')

    merged_gw_df = gw_data.merge(gw_data_rankers, on=['Gameweek','Rank'], how='left', suffixes=('', '_rankers'))
    merged_mn_df = mn_data.merge(mn_data_rankers, on=['Month','Rank'], how='left', suffixes=('', '_rankers'))

    merged_gw_df['Total'] = 300 / merged_gw_df['Count']
    merged_mn_df['Total'] = 530 / merged_mn_df['Count']

    merged_gw_df.Total.fillna(0, inplace=True)
    merged_mn_df.Total.fillna(0, inplace=True)

    
    return merged_gw_df, merged_mn_df
    
