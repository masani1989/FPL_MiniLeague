"""FastAPI routers for the backend."""
import hmac

from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from telegram import Update

from backend import config
from backend.agent import OllamaAgent
from backend.models import ChatRequest, ChatResponse

from fastapi import BackgroundTasks

from backend.gameweek import get_recent_completed_gameweek
from continental_conquest.runner import run_league_gw, run_knockout_gw, finalize_groups
from last_man_standing.runner import run_lms_for_gw
from backend.scheduler import announce_lms_elimination, announce_cc_round


router = APIRouter()
agent = OllamaAgent()


@router.get("/health")
async def health(request: Request) -> dict:
    token = config.APP_HEALTH_TOKEN
    if token:
        header_value = request.headers.get("X-Health-Token")
        query_value = request.query_params.get("token")
        provided = header_value or query_value
        if not provided or not hmac.compare_digest(token, provided):
            raise HTTPException(status_code=401, detail="Unauthorized")
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent.chat(request.message, chat_id=request.chat_id)


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    secret = config.TELEGRAM_WEBHOOK_SECRET
    if secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not hmac.compare_digest(secret, header or ""):
            raise HTTPException(status_code=401, detail="Unauthorized")
    bot_app = request.app.state.telegram_app
    if bot_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    bot_app.update_queue.put_nowait(update)
    return {"ok": True}



@router.post("/admin/run-contest-jobs")
async def run_contest_jobs(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Manually trigger LMS and CC scoring for the most recently completed GW."""
    token = config.APP_HEALTH_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="APP_HEALTH_TOKEN not configured")

    header_value = request.headers.get("X-Admin-Token")
    query_value = request.query_params.get("token")
    provided = header_value or query_value
    if not provided or not hmac.compare_digest(token, provided):
        raise HTTPException(status_code=401, detail="Unauthorized")

    async def _run() -> None:
        recent_gw, is_finished = await get_recent_completed_gameweek()
        if not is_finished or not recent_gw:
            return
        await run_lms_for_gw(recent_gw)
        if recent_gw <= 31:
            await run_league_gw(recent_gw)
        else:
            if recent_gw == 32:
                await finalize_groups()
            await run_knockout_gw(recent_gw)

    background_tasks.add_task(_run)
    return {"status": "scheduled"}




@router.post("/admin/run-announcements")
async def run_announcements(request: Request) -> dict:
    token = config.APP_HEALTH_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="APP_HEALTH_TOKEN not configured")

    header_value = request.headers.get("X-Admin-Token")
    query_value = request.query_params.get("token")
    provided = header_value or query_value
    if not provided or not hmac.compare_digest(token, provided):
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_app = request.app.state.telegram_app
    await announce_lms_elimination(telegram_app)
    await announce_cc_round(telegram_app)
    return {"status": "ok"}
