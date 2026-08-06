from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    chat_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict] | None = None


class Announcement(BaseModel):
    kind: str
    text: str
    chat_id: str
