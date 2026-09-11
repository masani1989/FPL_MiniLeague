import asyncio
import os

from backend import db
from backend.telegram_bot import build_telegram_app
from backend.scheduler import announce_cc_fixtures, announce_cc_round, announce_gameweek_results, announce_monthly_results, pre_gameweek_suggestions

async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    telegram_app = build_telegram_app(token)
    # await announce_cc_fixtures(telegram_app)
    # await announce_cc_round(telegram_app)
    # await pre_gameweek_suggestions(telegram_app)
    # await announce_gameweek_results(telegram_app)
    # await announce_monthly_results(telegram_app)


if __name__ == "__main__":
    asyncio.run(main())