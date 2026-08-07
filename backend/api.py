"""FastAPI routers for the backend."""
from fastapi import APIRouter, Request, HTTPException

from backend import config
from backend.agent import OllamaAgent
from backend.models import ChatRequest, ChatResponse


router = APIRouter()
agent = OllamaAgent()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent.chat(request.message, chat_id=request.chat_id)


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    secret = config.TELEGRAM_WEBHOOK_SECRET
    if secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != secret:
            raise HTTPException(status_code=401, detail="Unauthorized")
    bot_app = request.app.state.telegram_app
    if bot_app is None:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    data = await request.json()
    update = bot_app.bot.de_json(data, bot_app.bot)
    bot_app.update_queue.put_nowait(update)
    return {"ok": True}
