"""
One-time migration from Google Sheets to Supabase.
Run this locally after creating the Supabase project and running schema.sql.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import Utils.gsheet_conn as gs
import Utils.supabase_conn as db
from Utils.league import league
import Utils.gameweek as gwk
from Utils import config


def main():
    lg = league(config.FPL_LEAGUE_ID)
    league_id = db.sync_league(config.SEASON_ID, config.FPL_LEAGUE_ID, lg.get_league_name())

    # Sync managers from the FPL API.
    players = lg.get_league_players()
    players_df = pd.DataFrame.from_records(players).rename(
        columns={"Id": "PlayerId", "Player": "Player", "Team": "Team"}
    )
    manager_id_map = db.sync_managers(league_id, players_df)

    # Sync gameweeks from the FPL API bootstrap-static.
    gw_events = gwk.get_gameweek_data()["events"]
    gameweeks_df = pd.DataFrame([
        {
            "FplGameweekId": gw["id"],
            "Name": f"Gameweek {gw['id']}",
            "DeadlineTime": gw["deadline_time"],
            "Finished": gw["finished"],
            "IsCurrent": gw["is_current"],
        }
        for gw in gw_events
    ])
    gameweek_id_map = db.sync_gameweeks(config.SEASON_ID, gameweeks_df)

    # Overall sheet does not include PlayerId, so map from the league API by name.
    print("Loading Overall sheet...")
    ovr = gs.data_load('Overall', ['Rank', 'Player', 'Points', 'Last_Rank']).astype(
        {'Rank': 'int64', 'Last_Rank': 'int64', 'Points': 'int64'}
    )
    name_to_id = {name: fpl_id for fpl_id, name in players_df.set_index('PlayerId')['Player'].to_dict().items()}
    ovr['PlayerId'] = ovr['Player'].map(name_to_id)
    missing = ovr[ovr['PlayerId'].isna()]
    if not missing.empty:
        print("Warning: could not map player IDs for:", missing['Player'].tolist())
    db.upsert_overall(ovr, manager_id_map, config.SEASON_ID)
    print(f"Upserted {len(ovr)} overall rows.")

    # Gameweek sheet includes PlayerId.
    print("Loading Gameweek sheet...")
    gw = gs.data_load('Gameweek', ['PlayerId', 'Player', 'Gross', 'Transfer', 'Points', 'Rank', 'Gameweek']).astype(
        {'PlayerId': 'int64', 'Gameweek': 'int64', 'Points': 'int64', 'Gross': 'int64', 'Transfer': 'int64', 'Rank': 'int64'}
    )
    db.upsert_gameweek(gw, manager_id_map, gameweek_id_map, config.SEASON_ID)
    print(f"Upserted {len(gw)} gameweek rows.")

    # Monthly sheet includes PlayerId.
    print("Loading Monthly sheet...")
    mn = gs.data_load('Monthly', ['PlayerId', 'Player', 'Points', 'Rank', 'Month']).astype(
        {'PlayerId': 'int64', 'Points': 'int64', 'Rank': 'int64'}
    )
    db.upsert_monthly(mn, manager_id_map, config.SEASON_ID)
    print(f"Upserted {len(mn)} monthly rows.")

    # Refresh timestamp.
    print("Loading DataDate sheet...")
    data_date = gs.data_load('DataDate', ['DataAsOf'])
    if not data_date.empty:
        raw = str(data_date.loc[0, 'DataAsOf']).strip()
        for fmt in ('%m/%d/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                refreshed_at = pd.to_datetime(raw, format=fmt)
                break
            except ValueError:
                continue
        else:
            refreshed_at = pd.to_datetime(raw)

        current_gw = gwk.get_recent_completed_gameweek()
        gw_id = gameweek_id_map.get(current_gw[0]) if current_gw else None
        db.log_data_refresh(
            gameweek_id=gw_id,
            status="migrated",
            notes=f"Migrated from Google Sheets on {refreshed_at.isoformat()}",
        )
        print(f"Logged migration refresh: {refreshed_at}")

    print("Migration complete.")


if __name__ == '__main__':
    main()
