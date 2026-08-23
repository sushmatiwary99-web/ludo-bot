"""
main.py
Runs the Telegram bot (polling) and the FastAPI web app in the SAME
process, on the SAME asyncio loop. This exists so the whole project can
be deployed as a single Railway/Render service instead of two — much
simpler when you're managing everything from a phone.

Start command (Railway/Procfile): python main.py
Required env vars: BOT_TOKEN, WEBAPP_URL (see README "Deploying on Railway")
"""

import asyncio
import os
import logging

import uvicorn

from bot import bot, dp
import database as db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ludo-main")


async def run_api():
    import api  # imports the FastAPI `app` object
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(api.app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    await dp.start_polling(bot)


async def main():
    db.init_db()
    if not os.environ.get("WEBAPP_URL"):
        log.warning(
            "WEBAPP_URL is not set — the bot's Play button will not open a "
            "working Mini App until you set it to this service's public URL."
        )
    await asyncio.gather(run_api(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
