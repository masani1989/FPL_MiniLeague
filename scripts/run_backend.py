"""CLI entrypoint to start the FastAPI backend + Telegram scheduler."""
import uvicorn

from backend.config import PORT
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
