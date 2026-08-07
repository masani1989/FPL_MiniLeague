"""CLI entrypoint to start the FastAPI backend + Telegram scheduler."""
import os

import uvicorn

from backend.config import PORT
from backend.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
