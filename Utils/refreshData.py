import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Utils.gsheet_conn as gs
from Utils.league import *
import Utils.gameweek as gwk
import pandas as pd
import argparse


lg = league(282978)


def append_rows(sheet_name, wksheet_name, val):
    """
    Append rows to an existing googlesheet
    :param sheet_name: Workbook name
    :param wksheet_name: Worksheet name
    :param val: List of values to be appended
    :return:
    """
    client = gs.authenticate_google_sheets()
    sheet = client.open(sheet_name).worksheet(wksheet_name)
    sheet.append_rows(val, insert_data_option='INSERT_ROWS')


def delete_rows_based_on_column(sheet_name, wksheet_name, column_index, value_to_delete):
    """
    Delete rows from a googlesheet
    :param sheet_name: Workbook Name
    :param wksheet_name: Worksheet Name
    :param column_index: Column index number
    :param value_to_delete: Row to be deleted
    :return:
    """
    client = gs.authenticate_google_sheets()
    sheet = client.open(sheet_name).worksheet(wksheet_name)

    # Get all data from the sheet
    data = sheet.get_all_values()

    # Find the rows that match the value to delete
    rows_to_delete = []
    for index, row in enumerate(data):
        if row[column_index - 1] == value_to_delete:  # Convert to 0-based index
            rows_to_delete.append(index + 1)  # Store 1-based row indices

    # Delete rows starting from the last one to avoid shifting issues
    for row_index in reversed(rows_to_delete):
        sheet.delete_rows(row_index)


def refGw(gw=None):
    """
    Function to refresh the latest ongoing/completed gameweek's data
    :return:
    """
    plList = lg.get_league_players()
    currGw = gwk.get_recent_completed_gameweek() # [gw, True]

    delete_rows_based_on_column('FPL_Fantasy_Kings', 'Gameweek', 7, f'{currGw[0]}')
    gw_plr_list = []

    for i in plList:
        plr_dict = gwk.get_gw_data(i, currGw[0])
        gw_plr_list.append(plr_dict)

    gw_df = pd.DataFrame.from_records(gw_plr_list)
    gw_df['Rank'] = gw_df.groupby('Gameweek')['Points'].rank(ascending=False, method='dense')

    append_rows('FPL_Fantasy_Kings', 'Gameweek', gw_df.values.tolist())
    refMnth(currGw[0])
    refOverall()


def refMnth(g):
    """
    Function to refresh data for all month's up until ongoing one
    :return:
    """
    phases = gwk.get_phases()
    gw_mnth_lkp = pd.DataFrame(columns=['Gameweek', 'Month'])
    for i in range(1, g + 1):
        for k, v in phases.items():
            if v[0] <= i <= v[1] and k != 'Overall':
                df_temp = pd.DataFrame([{'Gameweek': i, 'Month': k}])
                gw_mnth_lkp = pd.concat([gw_mnth_lkp, df_temp], ignore_index=True).sort_values(by=['Gameweek'])

    latest_gw = gs.data_load('Gameweek', ['PlayerId', 'Player', 'Points', 'Gameweek']).astype(
        {'Gameweek': 'int64', 'Points': 'int64'})
    merged_df = pd.merge(latest_gw, gw_mnth_lkp, on='Gameweek')

    merged_mth_df = merged_df.groupby(['PlayerId', 'Player', 'Month'])['Points'].sum().reset_index()
    merged_mth_df['Rank'] = merged_mth_df.groupby(['Month'])['Points'].rank(method='dense', ascending=False)

    gs.update_data('Monthly', merged_mth_df)


def refOverall():
    """
    Function to refresh the overall points and rank data
    :return:
    """
    standings_df = lg.get_league_standings()
    gs.update_data('Overall', standings_df)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Refresh FPL Data')
    parser.add_argument('--gw', type=int, help='Gameweek number to refresh data for', required=False)
    args = parser.parse_args()
    if args.gw:
        refGw(args.gw)
        # refMnth(args.gw)
        # refOverall()
    else:
        refMnth(17)
