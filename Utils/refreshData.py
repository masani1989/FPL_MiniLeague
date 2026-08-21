import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Utils.league import *
import Utils.gameweek as gwk
import Utils.supabase_conn as db
from Utils import config
import pandas as pd
import argparse
import asyncio
from last_man_standing.runner import run_lms_for_gw
from continental_conquest.runner import run_league_gw, run_knockout_gw, finalize_groups


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
    """Refresh the latest ongoing/completed gameweek's data.

    If `gw` is provided, refresh that specific gameweek and treat it as finished
    for logging purposes. If not, use the most recent gameweek returned by the
    FPL API.
    """
    league_id, manager_id_map, gameweek_id_map = _ensure_reference_tables()
    plList = lg.get_league_players()

    if gw is None:
        currGw = gwk.get_recent_completed_gameweek()
    else:
        currGw = [gw, True]

    db.delete_gameweek(currGw[0], gameweek_id_map)
    gw_plr_list = []

    for i in plList:
        plr_dict = gwk.get_gw_data(i, currGw[0])
        gw_plr_list.append(plr_dict)

    gw_df = pd.DataFrame.from_records(gw_plr_list)
    if not gw_df.empty:
        gw_df['Rank'] = gw_df.groupby('Gameweek')['Points'].rank(ascending=False, method='dense')

        db.upsert_gameweek(gw_df, manager_id_map, gameweek_id_map, config.SEASON_ID)
        refMnth(currGw[0], manager_id_map, gameweek_id_map)
        refOverall(manager_id_map)
        refLms(currGw[0])
        try:
            refCc(currGw[0])
        except Exception:
            pass   # CC failure must not break the existing refresh or skip the success log
        db.log_data_refresh(
            gameweek_id=gameweek_id_map.get(currGw[0]),
            status="success",
            notes=f"refGw completed for gameweek {currGw[0]} (finished={currGw[1]})",
        )

    else:
        db.log_data_refresh(
            gameweek_id=gameweek_id_map.get(currGw[0]),
            status="failure",
            notes=f"refGw failed for gameweek {currGw[0]} (finished={currGw[1]})",
        )


def _compute_and_upsert_winnings(
    manager_id_map: dict[int, int],
    gameweek_id_map: dict[int, int],
    latest_gw: list,
) -> None:
    """Recompute and persist all winnings after stats have been refreshed."""
    import Utils.winnings as winnings

    gameweeks = db.load_gameweeks_df(config.SEASON_ID)

    gw_results = db.load_gameweek_for_refresh(config.SEASON_ID)
    gw_winnings = winnings.compute_gw_winnings(gw_results, gameweeks)
    db.upsert_gw_winnings(gw_winnings, manager_id_map, gameweek_id_map, config.SEASON_ID)

    monthly_results = db.load_monthly_for_refresh(config.SEASON_ID)
    mn_winnings = winnings.compute_monthly_winnings(monthly_results, latest_gw)
    db.upsert_monthly_winnings(mn_winnings, manager_id_map, config.SEASON_ID)

    overall_results = db.load_overall_for_refresh(config.SEASON_ID)
    prizes = winnings.compute_overall_prizes(overall_results, latest_gw)
    db.upsert_overall_prizes(prizes, manager_id_map, config.SEASON_ID)

    summary = winnings.compute_winnings_summary(gw_winnings, mn_winnings, prizes)
    db.upsert_winnings_summary(summary, manager_id_map, config.SEASON_ID)


def refresh_all():
    """End-to-end refresh used by GitHub Actions and the UI refresh button.

    Steps:
      1. Sync reference tables.
      2. Refresh the latest gameweek stats (which also refreshes monthly + overall).
      3. Recompute and persist winnings.
    """
    league_id, manager_id_map, gameweek_id_map = _ensure_reference_tables()
    latest_gw = gwk.get_recent_completed_gameweek()

    refGw(gw=latest_gw[0])
    _compute_and_upsert_winnings(manager_id_map, gameweek_id_map, latest_gw)


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


def refLms(gw=None, season_id=config.SEASON_ID):
    """Run the Last Man Standing elimination for a gameweek.

    If `gw` is None, target the most recent completed gameweek and skip when
    it is not yet finished. The runner is idempotent (upserts), so re-running
    a finished gameweek is safe.
    """
    if gw is None:
        recent = gwk.get_recent_completed_gameweek()
        gw = recent[0]
        if not recent[1]:
            return None
    return asyncio.run(run_lms_for_gw(gw, season_id=season_id))


def refCc(gw=None, season_id=config.SEASON_ID):
    """Run Continental Conquest for a gameweek (league or knockout).

    Idempotent (upserts). Error-isolated: callers (refGw) MUST wrap this in
    try/except so a CC failure never breaks the existing refresh or skips
    the success log.
    """
    if gw is None:
        recent = gwk.get_recent_completed_gameweek()
        gw = recent[0]
        if not recent[1]:
            return None
    if gw <= 31:
        return asyncio.run(run_league_gw(gw, season_id=season_id))
    if gw == 32:
        asyncio.run(finalize_groups(season_id=season_id))
    return asyncio.run(run_knockout_gw(gw, season_id=season_id))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Refresh FPL data in Supabase')
    parser.add_argument('--gw', type=int, help='Specific gameweek to refresh', required=False)
    parser.add_argument('--all', action='store_true', help='Refresh latest gameweek and recompute winnings')
    parser.add_argument('--lms', action='store_true', help='Run only the Last Man Standing refresh for the latest (or --gw) gameweek')
    parser.add_argument('--cc', action='store_true', help='Run only the Continental Conquest refresh for the latest (or --gw) gameweek')
    args = parser.parse_args()

    if args.lms:
        refLms(args.gw)
    elif args.cc:
        refCc(args.gw)
    elif args.gw:
        refGw(args.gw)
    else:
        refresh_all()
