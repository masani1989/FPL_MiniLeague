from datetime import datetime, timedelta
from typing import List, Any
import requests
import pandas as pd
from Params import params as p
import logging
import streamlit as st

logging.basicConfig(level=logging.INFO)

@st.cache_data()
def get_gameweek_data():
    """
    Function to get all gameweek's data
    :return: Json data with all gameweek info
    """

    session = requests.session()
    data = session.get(f'{p.base_url}bootstrap-static/').json()
    logging.info('API access successful!!')

    return data


def get_upcoming_deadline():
    """
    Get the deadline time for upcoming gameweek
    :return: deadline in IST timestamp
    """

    gameweeks = get_gameweek_data()['events']
    gw_df = pd.DataFrame.from_records(gameweeks).sort_values(by=['id'], ascending=True)

    now = datetime.utcnow()

    for index, row in gw_df.iterrows():
        if datetime.strptime(row['deadline_time'], '%Y-%m-%dT%H:%M:%SZ') > now:
            return datetime.strptime(row['deadline_time'], '%Y-%m-%dT%H:%M:%SZ') + timedelta(minutes=330)

def get_recent_completed_gameweek():
    """
    Get the most recent gameweek
    :return: List with gameweek ID and its status (True if completed, False if in-progress)
    """

    gameweeks = get_gameweek_data()['events']
    gw_df = pd.DataFrame.from_records(gameweeks).sort_values(by=['id'], ascending=False)

    now = datetime.utcnow()

    try:
        for index, row in gw_df.iterrows():
            if datetime.strptime(row['deadline_time'], '%Y-%m-%dT%H:%M:%SZ') < now:
                logging.info('==========  Gameweek Details  ==========')
                logging.info('Gameweek ID: ' + str(row['id']))
                logging.info('Deadline Time: ' + str(datetime.strptime(row['deadline_time'], '%Y-%m-%dT%H:%M:%SZ')))
                logging.info('Gameweek Status: ' + str(row['finished']))
                logging.info('========================================')
                # Return the gameweek ID and its status
                return [row['id'], row['finished']]
    
    except Exception as e:
        logging.info('Error occurred: ' + str(e))

    # If no completed gameweek found, return default
    logging.info('No completed gameweek found before ' + str(now))
    return [0, False]


def get_phases():
    """
    List all the phases
    :return: Dictionary of Months and GW Start/Stop numbers
    """

    phases = get_gameweek_data()['phases']
    gw = {}

    for phase in phases:
        if phase['name'] != 'Overall':
            gw[phase['name']] = [phase['start_event']] + [phase['stop_event']]

    return gw


def get_till_latest_phase():
    """
    Get the latest and completed phase's month name
    :return: list of month values
    """

    phase = get_phases()
    gw = get_recent_completed_gameweek()

    months = {}

    try:
        for (k, v) in phase.items():
            if gw[0] > v[1] or (gw[0] == v[1] and gw[1]):
                months[k] = v
        if months:
            return months

    except Exception as e:
        logging.error(e)


def get_ongoing_month():
    """
    Get the recently completed month details
    :return:
    """
    gw = get_recent_completed_gameweek()
    mn = get_till_latest_phase()
    
    for k, v in mn.items():
        if ((gw[0] == v[1] and not gw[1]) or gw[0] < v[1]):
            return k
        else:
            return datetime.utcnow().strftime('%B')


def get_gw_data(player, gw) -> dict:
    """
    Function to get data from fpl for mentioned gameweek and prepare data points from it per manager
    :param player: player id
    :param gw: gameweek number
    :return: dictionary of values for each player
    """
    pgw_dict = {}

    manager_history_url = f'{p.base_url}entry/'
    session = requests.session()
    x = session.get(manager_history_url + str(player['Id']) + '/history/').json()
    for event in x['current']:
        if event['event'] == gw:
            playerName = player['Player'].split(' ')[0].capitalize() + ' ' + player['Player'].split(' ')[1].capitalize()
            gross = event['points']
            transfer = event['event_transfers_cost']
            netPoints = event['points'] - event['event_transfers_cost']
            pgw_dict = {'PlayerId': player['Id'], 'Player': playerName, 'Gross': gross, 'Transfer': transfer,
                        'Points': netPoints, 'Rank': '', 'Gameweek': gw}

    return pgw_dict


if __name__ == '__main__':
    print('\n', '*'*100, '\n', '------Upcoming Deadline: ', get_upcoming_deadline(), '------', '\n', '*'*100, '\n')
    print('\n', '*'*100, '\n', '------Recent completed gameweek: ', get_recent_completed_gameweek(), '------', '\n', '*'*100, '\n')
    print('\n', '*'*100, '\n', '------Phases: ', get_phases(), '------', '\n', '*'*100, '\n')
    print('\n', '*'*100, '\n', '------Till Latest Phase: ', get_till_latest_phase(), '------', '\n', '*'*100, '\n')
    print('\n', '*'*100, '\n', '------Ongoing Month: ', get_ongoing_month(), '------', '\n', '*'*100, '\n')
    print(get_gw_data({'Id': 777321, 'Team': 'Roger XI', 'Player': 'Himanshu Masani'}, 38))
