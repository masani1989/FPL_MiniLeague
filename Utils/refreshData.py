import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Utils.league import *
import Utils.gameweek as gwk
import Utils.supabase_conn as db
from Utils import config
import pandas as pd
import argparse


lg = league(config.FPL_LEAGUE_ID)


def _ensure_reference_tables():
    """Sync league, managers and gameweeks before writing stats.

    Returns (league_id, manager_id_map, gameweek_id_map).
    """
    league_id = db.sync_league(config.SEASON_ID, config.FPL_LEAGUE_ID, config.LEAGUE_NAME)

    players = lg.get_league_players()
    players_df = pd.DataFrame.from_records(players).rename(
        columns={"Id": "PlayerId", "Player": "Player", "Team": "Team"}
    )
    manager_id_map = db.sync_managers(league_id, players_df)

    gw_data = gwk.get_gameweek_data()["events"]
    gameweeks_df = pd.DataFrame([
        {
            "FplGameweekId": gw["id"],
            "Name": f"Gameweek {gw['id']}",
            "DeadlineTime": gw["deadline_time"],
            "Finished": gw["finished"],
            "IsCurrent": gw["is_current"],
        }
        for gw in gw_data
    ])
    gameweek_id_map = db.sync_gameweeks(config.SEASON_ID, gameweeks_df)

    return league_id, manager_id_map, gameweek_id_map


def refGw(gw=None):
    """Refresh the latest ongoing/completed gameweek's data."""
    league_id, manager_id_map, gameweek_id_map = _ensure_reference_tables()
    plList = lg.get_league_players()
    currGw = gwk.get_recent_completed_gameweek()

    db.delete_gameweek(currGw[0], gameweek_id_map)
    gw_plr_list = []

    for i in plList:
        plr_dict = gwk.get_gw_data(i, currGw[0])
        gw_plr_list.append(plr_dict)

    gw_df = pd.DataFrame.from_records(gw_plr_list)
    gw_df['Rank'] = gw_df.groupby('Gameweek')['Points'].rank(ascending=False, method='dense')

    db.upsert_gameweek(gw_df, manager_id_map, gameweek_id_map, config.SEASON_ID)
    refMnth(currGw[0], manager_id_map, gameweek_id_map)
    refOverall(manager_id_map)
    db.log_data_refresh(
        gameweek_id=gameweek_id_map.get(currGw[0]),
        status="success",
        notes="refGw completed",
    )


def refMnth(g, manager_id_map=None, gameweek_id_map=None):
    """Refresh monthly results for all months up to the ongoing one."""
    if manager_id_map is None or gameweek_id_map is None:
        _, manager_id_map, gameweek_id_map = _ensure_reference_tables()

    phases = gwk.get_phases()
    gw_mnth_lkp = pd.DataFrame(columns=['Gameweek', 'Month'])
    for i in range(1, g + 1):
        for k, v in phases.items():
            if v[0] <= i <= v[1] and k != 'Overall':
                df_temp = pd.DataFrame([{'Gameweek': i, 'Month': k}])
                gw_mnth_lkp = pd.concat([gw_mnth_lkp, df_temp], ignore_index=True).sort_values(by=['Gameweek'])

    latest_gw = db.load_gameweek_for_refresh().astype(
        {'Gameweek': 'int64', 'Points': 'int64'}
    )
    merged_df = pd.merge(latest_gw, gw_mnth_lkp, on='Gameweek')

    merged_mth_df = merged_df.groupby(['PlayerId', 'Player', 'Month'])['Points'].sum().reset_index()
    merged_mth_df['Rank'] = merged_mth_df.groupby(['Month'])['Points'].rank(method='dense', ascending=False)

    db.upsert_monthly(merged_mth_df, manager_id_map, config.SEASON_ID)


def refOverall(manager_id_map=None):
    """Refresh overall points and rank data."""
    if manager_id_map is None:
        _, manager_id_map, _ = _ensure_reference_tables()

    standings_df = lg.get_league_standings()
    db.upsert_overall(standings_df, manager_id_map, config.SEASON_ID)


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
