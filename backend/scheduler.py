"""Scheduled announcements for the Telegram bot."""
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend import config, db
from backend.agent import OllamaAgent
from backend.fpl_client import FPLClient
from backend.gameweek import get_phases, get_recent_completed_gameweek
from backend.tools.mini_league import get_standings
from last_man_standing.runner import run_lms_for_gw
from continental_conquest.runner import run_league_gw, run_knockout_gw, finalize_groups


scheduler = AsyncIOScheduler()


def start_scheduler(telegram_app) -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        announce_upcoming_deadline,
        "cron",
        minute="7",
        args=(telegram_app,),
        id="announce_deadline",
        replace_existing=True,
    )
    scheduler.add_job(
        announce_gameweek_results,
        "cron",
        minute="17",
        args=(telegram_app,),
        id="announce_gw_results",
        replace_existing=True,
    )
    scheduler.add_job(
        announce_monthly_results,
        "cron",
        minute="27",
        args=(telegram_app,),
        id="announce_monthly_results",
        replace_existing=True,
    )
    scheduler.add_job(
        pre_gameweek_suggestions,
        "cron",
        minute="37",
        args=(telegram_app,),
        id="pre_gw_suggestions",
        replace_existing=True,
    )
    scheduler.add_job(
        announce_lms_elimination,
        "cron",
        minute="47",
        args=(telegram_app,),
        id="announce_lms_elimination",
        replace_existing=True,
    )
    scheduler.add_job(
        announce_cc_round,
        "cron",
        minute="7",
        args=(telegram_app,),
        id="announce_cc_round",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()


async def _send_to_active_chats(telegram_app, text: str, kind: str, trigger_key: str) -> None:
    if telegram_app is None:
        return
    allowed = config.allowed_telegram_chat_ids()
    chats = await db.get_telegram_chats()
    for chat in chats:
        chat_id = chat["chat_id"]
        if allowed and chat_id not in allowed:
            continue
        if await db.announcement_already_posted(chat_id, kind, trigger_key):
            continue
        try:
            await telegram_app.bot.send_message(chat_id=chat_id, text=text[:4000])
            await db.log_announcement(chat_id, kind, trigger_key, text)
        except Exception:
            # Log and continue; do not crash the scheduler.
            pass


def _parse_deadline(deadline: str) -> datetime:
    return datetime.fromisoformat(deadline.replace("Z", "+00:00"))


async def announce_upcoming_deadline(telegram_app) -> None:
    if telegram_app is None:
        return
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    now_utc = datetime.now(timezone.utc)
    for gw in bootstrap.get("events", []):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        deadline_dt = _parse_deadline(deadline)
        # if deadline_dt > now_utc and (deadline_dt - now_utc).total_seconds() <= 1034460:
        #     text = f"⏰ Gameweek {gw['id']} deadline is at {deadline_dt.strftime('%d %b %H:%M UTC')}!"
        #     await _send_to_active_chats(telegram_app, text, "deadline", f"gw_{gw['id']}")
        #     return

        # Only announce the next upcoming deadline, and only within 2 days of it.
        if deadline_dt > now_utc:
            seconds_until = (deadline_dt - now_utc).total_seconds()
            if 0 < seconds_until <= 172800:
                text = f"⏰ Gameweek {gw['id']} deadline is at {(deadline_dt + timedelta(minutes=330)).strftime('%d %b %H:%M')}!"
                await _send_to_active_chats(telegram_app, text, "deadline", f"gw_{gw['id']}")
            return


async def announce_gameweek_results(telegram_app) -> None:
    if telegram_app is None:
        return
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    now_utc = datetime.now(timezone.utc)
    for gw in reversed(bootstrap.get("events", [])):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        deadline_dt = _parse_deadline(deadline)
        if gw.get("finished") and deadline_dt < now_utc:
            agent = OllamaAgent()
            response = await agent.chat(f"Summarise gameweek {gw['id']} results, top performers and winner(s)")
            await _send_to_active_chats(telegram_app, response.reply, "gw_results", f"gw_{gw['id']}")
            return


async def announce_monthly_results(telegram_app) -> None:
    """Announce monthly results once the most recently completed gameweek is the last one of a month."""
    if telegram_app is None:
        return
    recent_gw, is_finished = await get_recent_completed_gameweek()
    if not is_finished:
        return
    phases = await get_phases()
    for month_name, gws in phases.items():
        if recent_gw == gws[-1]:
            rows = await get_standings("monthly", month=month_name)
            if rows.get("standings"):
                agent = OllamaAgent()
                response = await agent.chat(f"Summarise the {month_name} monthly standings, top performers and winner(s)")
                await _send_to_active_chats(telegram_app, response.reply, "monthly_results", f"month_{month_name}")
            return


async def pre_gameweek_suggestions(telegram_app) -> None:
    if telegram_app is None:
        return
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    now_utc = datetime.now(timezone.utc)
    for gw in bootstrap.get("events", []):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        deadline_dt = _parse_deadline(deadline)
        if deadline_dt > now_utc and 0 < (deadline_dt - now_utc).total_seconds() <= 172800:
            agent = OllamaAgent()
            response = await agent.chat(f"Give captain and transfer suggestions for gameweek {gw['id']}")
            await _send_to_active_chats(telegram_app, response.reply, "pre_gw_suggestions", f"gw_{gw['id']}")
            return


async def announce_lms_elimination(telegram_app) -> None:
    """Run LMS elimination for the most-recent finished GW and announce the loser."""
    if telegram_app is None:
        return
    recent_gw, is_finished = await get_recent_completed_gameweek()
    if not is_finished or not recent_gw:
        return
    summary = await run_lms_for_gw(recent_gw)
    if summary.get("status") != "ok" or not summary.get("eliminated"):
        return
    eliminated = summary["eliminated"]
    gw = summary["gw"]
    alive = summary.get("alive", [])
    text = (
        f"🛡️ Last Man Standing — Gameweek {gw}:\n"
        f"❌ {eliminated['player_name']} has been eliminated!\n"
        f"🧍 {len(alive)} survivors remain."
    )
    if eliminated.get("coin_toss_required"):
        text += "\n🪙 Tie was decided by a coin toss."
    if summary.get("completed"):
        text += "\n🏆 We have a Last Man Standing winner!"
    await _send_to_active_chats(telegram_app, text, "lms_elimination", f"gw_{recent_gw}")


async def _cc_match_grid(matches: list[dict], recent_gw: int) -> str:
    """Format played matches for this GW as a Telegram-friendly grid."""
    lines: list[str] = []
    for m in matches:
        home = m.get("home_manager_name") or m.get("home_team_name") or "Home"
        away = m.get("away_manager_name") or m.get("away_team_name") or "Away"
        home_score = m.get("home_score")
        away_score = m.get("away_score")
        if home_score is None or away_score is None:
            continue
        lines.append(f"{home} {home_score} - {away_score} {away}")
    return "\n".join(lines) if lines else "No matches recorded."


async def _cc_group_standings_snippet(contest_id: int) -> str:
    """Return the latest group standings (Group A and Group B) as a short table."""
    groups = await db.get_cc_groups(contest_id)
    if not groups:
        return ""
    # Resolve stable A/B ordering by id if possible, otherwise by name.
    groups = sorted(groups, key=lambda g: (g.get("name", ""), g.get("id", 0)))
    sections: list[str] = []
    for g in groups:
        rows = await db.get_cc_standings(contest_id, g["id"])
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: r.get("group_rank", 0) or 0)
        name = g.get("name", "Group")
        sections.append(f"📊 {name}")
        for r in rows:
            rank = r.get("group_rank", "-")
            player = r.get("player_name") or r.get("team_name") or "Player"
            p = r.get("played", 0)
            pts = r.get("points", 0)
            gf = r.get("score_for", 0)
            ga = r.get("score_against", 0)
            qual = r.get("qualification") or ""
            q_emoji = " ✅" if qual and "ucl" in qual.lower() else " 🟠" if qual else " ❌"
            sections.append(f"{rank}. {player} — {p}P {pts}PTS ({gf}-{ga}){q_emoji}")
    return "\n".join(sections)


async def announce_cc_round(telegram_app) -> None:
    """Run Continental Conquest for the most-recent finished GW and post a detailed summary.

    League (gw<=31) scores matches; knockout (gw>=32) scores legs and resolves ties
    (finalizing the group phase at gw 32 first). Announces only when matches were
    actually scored. Deduped on gw_{recent_gw}.
    """
    if telegram_app is None:
        return
    recent_gw, is_finished = await get_recent_completed_gameweek()
    if not is_finished or not recent_gw:
        return
    if recent_gw <= 31:
        summary = await run_league_gw(recent_gw)
    else:
        if recent_gw == 32:
            await finalize_groups()
        summary = await run_knockout_gw(recent_gw)
    if summary.get("status") != "ok":
        return
    matches_played = summary.get("matches_scored", 0)
    if not matches_played:
        return

    contest_id = summary.get("contest_id")
    if not contest_id:
        contest = await db.get_cc_contest(config.SEASON_ID, config.FPL_LEAGUE_ID)
        contest_id = contest["id"] if contest else None

    matches = []
    if contest_id:
        matches = [
            m
            for m in await db.get_cc_matches_for_gw(contest_id, recent_gw)
            if m.get("played")
        ]

    header = f"⚽ Continental Conquest — Gameweek {recent_gw}"
    subheader = f"{matches_played} match(es) played"
    grid = await _cc_match_grid(matches, recent_gw)

    parts = [header, subheader, "", "🗓️ Results:", grid]
    if recent_gw <= 31 and contest_id:
        standings = await _cc_group_standings_snippet(contest_id)
        if standings:
            parts.extend(["", "🏆 Standings:", standings])

    text = "\n".join(parts)
    await _send_to_active_chats(telegram_app, text, "cc_round", f"gw_{recent_gw}")
