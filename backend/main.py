from fastapi import FastAPI

from backend.models import ChatRequest, ChatResponse

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(reply=f"Echo: {request.message}")
