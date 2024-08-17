from datetime import datetime, timedelta
from typing import List, Any

import requests
import pandas as pd
from Params import params as p
import logging

logging.basicConfig(level=logging.INFO)


def get_gameweek_data():
    """
    Function to get all gameweek's data
    :return: Json data with all gameweek info
    """

    session = requests.session()
    data = session.get(f'{p.base_url}bootstrap-static/').json()
    logging.info('API access successful!!')

    return data


def get_recent_completed_gameweek():
    """
    Get the most recent gameweek's ID & it's status.
    :return: Gameweek number and status
    """

    gameweeks = get_gameweek_data()['events']
    gw_df = pd.DataFrame.from_records(gameweeks).sort_values(by=['id'], ascending=False)

    now = datetime.utcnow()  # + timedelta(days=45)

    for index, row in gw_df.iterrows():
        if datetime.strptime(row['deadline_time'], '%Y-%m-%dT%H:%M:%SZ') < now:
            val = str(row['id']) + ' - ' + row['deadline_time'] + ' - ' + str(row['finished'])
            logging.info('Gameweek Details  ----> ' + val)

            return [row['id'], row['finished']]


def get_phases():
    """
    List all the phases
    :return: Dictionary of Months and GW Start/Stop numbers
    """

    phases = get_gameweek_data()['phases']
    gw = {}

    for phase in phases:
        gw[phase['name']] = [phase['start_event']] + [phase['stop_event']]

    return gw


def get_till_latest_phase():
    """
    Get the latest and completed phase's month name
    :return: list of month values
    """

    phase = get_phases()
    gw = get_recent_completed_gameweek()

    try:
        for (k, v) in phase.items():
            if v[0] <= gw[0] <= v[1] and k != 'Overall':
                return k, v

    except Exception as e:
        logging.error(e)


def get_gw_data(player, gw) -> dict:
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
    # return {'PlayerId': 123, 'Player': 'Himanshu Masani', 'Gross': 92, 'Transfer': 8,
    #         'Points': 84, 'Rank': '', 'Gameweek': 23}


if __name__ == '__main__':
    print(get_recent_completed_gameweek())
    print(get_phases())
    print(get_till_latest_phase())
