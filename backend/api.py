"""FastAPI routers for the backend."""
from fastapi import APIRouter, Request

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
    bot_app = request.app.state.telegram_app
    if bot_app is None:
        return {"error": "Telegram bot not configured"}
    data = await request.json()
    await bot_app.update_queue.put(bot_app.bot.de_json(data, bot_app.bot))
    return {"ok": True}
