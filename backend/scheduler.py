"""Scheduled announcements for the Telegram bot."""
import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend import db
from backend.agent import OllamaAgent
from backend.fpl_client import FPLClient
from backend.tools.mini_league import get_standings
from Utils.gameweek import get_phases, get_recent_completed_gameweek


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
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()


async def _send_to_active_chats(telegram_app, text: str, kind: str, trigger_key: str) -> None:
    if telegram_app is None:
        return
    chats = await db.get_telegram_chats()
    for chat in chats:
        chat_id = chat["chat_id"]
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
    client = FPLClient()
    bootstrap = await client.get_bootstrap_static()
    now_utc = datetime.now(timezone.utc)
    for gw in bootstrap.get("events", []):
        deadline = gw.get("deadline_time")
        if not deadline:
            continue
        deadline_dt = _parse_deadline(deadline)
        if deadline_dt > now_utc and (deadline_dt - now_utc).total_seconds() <= 86400:
            text = f"⏰ Gameweek {gw['id']} deadline is at {deadline_dt.strftime('%d %b %H:%M UTC')}!"
            await _send_to_active_chats(telegram_app, text, "deadline", f"gw_{gw['id']}")
            return


async def announce_gameweek_results(telegram_app) -> None:
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
            response = await agent.chat(f"Summarise gameweek {gw['id']} results and top performers")
            await _send_to_active_chats(telegram_app, response.reply, "gw_results", f"gw_{gw['id']}")
            return


async def announce_monthly_results(telegram_app) -> None:
    """Announce monthly results once the most recently completed gameweek is the last one of a month."""
    loop = asyncio.get_running_loop()
    recent_gw, is_finished = await loop.run_in_executor(None, get_recent_completed_gameweek)
    if not is_finished:
        return
    phases = get_phases()
    for month_name, gws in phases.items():
        if recent_gw == gws[-1]:
            rows = await get_standings("monthly", month=month_name)
            if rows.get("standings"):
                agent = OllamaAgent()
                response = await agent.chat(f"Summarise the {month_name} monthly standings")
                await _send_to_active_chats(telegram_app, response.reply, "monthly_results", f"month_{month_name}")
            return


async def pre_gameweek_suggestions(telegram_app) -> None:
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
