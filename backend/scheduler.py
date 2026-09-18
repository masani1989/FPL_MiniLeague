"""Scheduled announcements for the Telegram bot."""
import io
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend import config, db
from backend.agent import OllamaAgent
from backend.fpl_client import FPLClient
from backend.gameweek import get_phases, get_recent_completed_gameweek
from backend.tools.mini_league import get_standings
from backend.tools.continental_conquest import get_cc_fixtures
from last_man_standing.runner import run_lms_for_gw
from continental_conquest.runner import run_league_gw, run_knockout_gw, finalize_groups

from backend.telegram_bot import _render_table_image


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
    scheduler.add_job(
        announce_cc_fixtures,
        "cron",
        minute="37",
        args=(telegram_app,),
        id="announce_cc_fixtures",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()


async def _send_to_active_chats(telegram_app, text: str, kind: str, trigger_key: str, photos: list[io.BytesIO] | None = None) -> None:
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
            if photos:
                for idx, photo in enumerate(photos):
                    photo.seek(0)
                    caption = text[:1024] if idx == 0 else None
                    await telegram_app.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            else:
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
            gw_res_prompt = f"Summarise gameweek {gw['id']} results. Announce winner(s) and top performers across each competition. " \
                            f"For continental conquest, mention the key results which were either very close, a complete dominance or a nailbiting draw (it needs to hold significance and not necessary to give results under each category). Do not provide standings and all the results from the gameweek. " \
                            f"For last man standing, mention the eliminated player and the number of survivors remaining. Do mention if the knockout was a close contest. " \
                            f"Make it presenatable for whatsapp and telegram. Avoid long paragraphs." \
                            " Use single * for bold. Do not use double ** or __ for bold."
            response = await agent.chat(gw_res_prompt)
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
                mn_res_prompt = f"Summarise the {month_name} monthly standings, top performers and winner(s). " \
                                f"Make it presenatable for whatsapp and telegram. Avoid long paragraphs." \
                                " Use single * for bold. Do not use double ** or __ for bold."
                response = await agent.chat(mn_res_prompt)
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
            pre_gw_prompt = f"Give captain and transfer suggestions for gameweek {gw['id']}. Consider recent form, FDR, and upcoming fixtures. Format the response as a concise list of suggestions with brief reasoning for each. Make it presenatable for whatsapp and telegram. Avoid long paragraphs. Mention Fixture Difficulty Rating (FDR) for each player for next 5 games in the suggestions. Do not use double ** or __ for bold. Use single * for bold."
            response = await agent.chat(pre_gw_prompt)
            await _send_to_active_chats(telegram_app, response.reply, "pre_gw_suggestions", f"gw_{gw['id']}")
            return


async def announce_lms_elimination(telegram_app) -> None:
    """Run LMS elimination for the most-recent finished GW and announce the loser."""
    if telegram_app is None:
        return
    recent_gw, is_finished = await get_recent_completed_gameweek()
    if not is_finished or not recent_gw:
        return

    # if gameweek is already processed, announce based on data in db lms tables
    if is_finished and recent_gw:
        contest = await db.get_lms_contest(config.SEASON_ID, config.FPL_LEAGUE_ID)
        db_result = await db.get_lms_eliminated_managers(contest["id"], recent_gw) if contest else None
        if not db_result:
            return
        eliminated_player_name = db_result[0]["player_name"]
        coin_toss_required = db_result[0]["coin_toss_required"]
        # alive_after = await db.get_lms_standings_rows(contest["id"]) if contest else None
        # alive_after = len(alive_after[alive_after["is_alive"] == True]) if alive_after else 0

        alive_after = await db.get_lms_standings_rows(contest["id"]) if contest else []
        alive_after_count = sum(1 for r in alive_after if r.get("is_alive")) if alive_after else 0

        if alive_after_count == 1:
            completed = True
        else:
            completed = False

        text = (
            f"🛡️ Last Man Standing — Gameweek {recent_gw}:\n"
            f"❌ {eliminated_player_name} has been eliminated!\n"
            f"🧍 {alive_after_count} survivors remain."
        )
        if coin_toss_required:
            text += "\n🪙 Tie was decided by a coin toss."
        if completed:
            text += "\n🏆 We have a Last Man Standing winner!"
        await _send_to_active_chats(telegram_app, text, "lms_elimination", f"gw_{recent_gw}")
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
    """Format matches as a Markdown table for image rendering."""
    if not matches:
        return "No matches recorded."
    lines = ["| Home | Score | Away |"]
    for m in matches:
        home = (m.get("home_manager_name") or "TBC").split()[0] + " " + (m.get("home_manager_name") or "TBC").split()[1][0]
        away = (m.get("away_manager_name") or "TBC").split()[0] + " " + (m.get("away_manager_name") or "TBC").split()[1][0]
        home_score = "" if m.get("home_score") is None else str(m["home_score"])
        away_score = "" if m.get("away_score") is None else str(m["away_score"])
        lines.append(f"| {home} | {home_score} - {away_score} | {away} |")
    return "\n".join(lines)


async def _cc_group_standings_snippet(contest_id: int, group_name: str = None) -> str:
    """Return the latest group standings as a single Markdown table."""
    groups = await db.get_cc_groups(contest_id)
    if not groups:
        return ""
    # Resolve stable A/B ordering by id if possible, otherwise by name.
    groups = sorted(groups, key=lambda g: (g.get("name", ""), g.get("id", 0)))
    lines = ["| Rank | Player | P | PTS | GF-GA | Q |"]
    for g in groups:
        rows = await db.get_cc_standings(contest_id, g["id"])
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: r.get("group_rank", 0) or 0)
        name = g.get("name", "")
        for r in rows:
            if group_name and name != group_name:
                continue
            rank = r.get("group_rank", "-")
            player = (r.get("player_name") or r.get("team_name") or "Player").split()[0] + " " + (r.get("player_name") or r.get("team_name") or "Player").split()[1][0]
            p = r.get("played", 0)
            pts = r.get("points", 0)
            gf = r.get("score_for", 0)
            ga = r.get("score_against", 0)
            qual = r.get("qualification") or ""
            q = (
                "UCL"
                if qual and "ucl" in qual.lower()
                else "UEL"
                if qual and "uel" in qual.lower()
                else "OUT"
            )
            lines.append(f"| {rank} | {player} | {p} | {pts} | {gf}-{ga} | {q} |")
    return "\n".join(lines) if len(lines) > 1 else ""


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

    header = f"🗓️ Results\n\nContinental Conquest — Gameweek {recent_gw}\n⚽ {matches_played} match(es) played"
    grid = await _cc_match_grid(matches, recent_gw)

    photos: list[io.BytesIO] = []
    results_photo = _render_table_image(f"🗓️ Results:\n{grid}")
    if results_photo and results_photo.getbuffer().nbytes > 0:
        photos.append(results_photo)

    await _send_to_active_chats(telegram_app, header, "cc_round_results", f"gw_{recent_gw}", photos=photos)

    groups = await db.get_cc_groups(contest_id) if contest_id else 0
    group_names = [g.get("name", "") for g in groups] if groups else []

    if recent_gw <= 31 and contest_id:
        for i in group_names:
            standings = await _cc_group_standings_snippet(contest_id, i)
            if standings:
                standings_photo = _render_table_image(f"🏆 Group {i} Standings:\n{standings}")
                if standings_photo and standings_photo.getbuffer().nbytes > 0:
                    photos: list[io.BytesIO] = []
                    photos.append(standings_photo)
                    await _send_to_active_chats(
                        telegram_app, f"🏆 Group {i} Standings", f"cc_round_standings_{i}", f"gw_{recent_gw}_group_{i}", photos=photos
                    )
        # standings = await _cc_group_standings_snippet(contest_id)
        # if standings:
        #     standings_photo = _render_table_image(f"🏆 Standings:\n{standings}")
        #     if standings_photo and standings_photo.getbuffer().nbytes > 0:
        #         photos: list[io.BytesIO] = []
        #         photos.append(standings_photo)

    # if photos:
    #     print("\n".join([header, grid]))  # For debugging/logging purposes
    #     await _send_to_active_chats(
    #         telegram_app, header, "cc_round", f"gw_{recent_gw}", photos=photos
    #     )

async def announce_cc_fixtures(telegram_app) -> None:
    """Announce the fixtures for the next GW of Continental Conquest."""
    if telegram_app is None:
        return
    recent_gw, is_finished = await get_recent_completed_gameweek()
    if not is_finished or not recent_gw:
        return
    next_gw = recent_gw + 1
    # announce only if next_gw deadline is within 2 days
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    next_gw_data = next((gw for gw in bootstrap.get("events", []) if gw.get("id") == next_gw), None)
    if not next_gw_data:
        return
    deadline = next_gw_data.get("deadline_time")
    if not deadline:
        return
    deadline_dt = _parse_deadline(deadline)
    now_utc = datetime.now(timezone.utc)
    if not (0 < (deadline_dt - now_utc).total_seconds() <= 172800):
        return
    contest = await db.get_cc_contest(config.SEASON_ID, config.FPL_LEAGUE_ID)
    if not contest:
        return
    print(f"Fetching CC fixtures for GW {next_gw}...")
    matches = await get_cc_fixtures(next_gw)
    if not matches:
        return

    header = f"⚽ Continental Conquest — Gameweek {next_gw} Fixtures"
    grid = await _cc_match_grid(matches.get("matches"), next_gw)
    photo = _render_table_image(f"🗓️ Fixtures:\n{grid}")
    # save photo to file for debugging
    # if photo and photo.getbuffer().nbytes > 0:
    #     with open(f"cc_fixtures_gw_{next_gw}.png", "wb") as f:
    #         f.write(photo.getbuffer())

    if photo and photo.getbuffer().nbytes > 0:
        await _send_to_active_chats(telegram_app, header, "upcoming_cc_fixtures", f"gw_{next_gw}", photos=[photo])

if __name__ == "__main__":
    import asyncio

    async def main():
        await announce_cc_fixtures("test")

    asyncio.run(main())