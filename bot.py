"""
bot.py
The Telegram-side of the Ludo bot: /start, referral links, /coins,
/invite, /leaderboard, and the button that opens the Mini App game.

Run with:  python bot.py
Requires env vars: BOT_TOKEN, WEBAPP_URL (public https URL of the deployed
FastAPI app that serves webapp/index.html, e.g. from api.py).
"""

import os
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.client.default import DefaultBotProperties
import asyncio

import database as db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ludo-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def play_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Play Ludo", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )


@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split(maxsplit=1)
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            candidate = int(args[1].removeprefix("ref_"))
            if candidate != message.from_user.id:
                referred_by = candidate
        except ValueError:
            pass

    user = db.get_or_create_user(
        message.from_user.id, message.from_user.username or "", referred_by
    )

    bonus_line = ""
    if referred_by and user["created_at"]:
        bonus_line = "\n🎁 You joined via a referral — +50 bonus coins!"

    await message.answer(
        f"🎲 <b>Welcome to Ludo Bash!</b>\n\n"
        f"Play free Ludo, earn coins, and unlock cosmetic dice, boards and tokens.\n"
        f"No real money ever — coins can't be withdrawn or cashed out, they're just for fun cosmetics.\n\n"
        f"💰 Balance: <b>{user['coins']} coins</b>{bonus_line}\n\n"
        f"Tap below to play 👇",
        reply_markup=play_keyboard(),
    )


@dp.message(Command("play"))
async def play(message: Message):
    await message.answer("🎲 Tap to open the board:", reply_markup=play_keyboard())


@dp.message(Command("coins"))
async def coins(message: Message):
    user = db.get_or_create_user(message.from_user.id, message.from_user.username or "")
    await message.answer(f"💰 You have <b>{user['coins']}</b> coins.")


@dp.message(Command("daily"))
async def daily(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username or "")
    ok, wait_left = db.try_claim_daily(message.from_user.id, amount=100)
    if ok:
        await message.answer("✅ Daily bonus claimed: <b>+100 coins</b>!")
    else:
        hours = wait_left // 3600
        mins = (wait_left % 3600) // 60
        await message.answer(f"⏳ Already claimed. Try again in {hours}h {mins}m.")


@dp.message(Command("invite"))
async def invite(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username or "")
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    await message.answer(
        "👥 <b>Invite friends, earn coins</b>\n\n"
        f"Share your link — you get <b>+100 coins</b> for every friend who joins:\n\n"
        f"{link}"
    )


@dp.message(Command("leaderboard"))
async def leaderboard(message: Message):
    top = db.leaderboard(10)
    lines = []
    for i, row in enumerate(top, start=1):
        name = row["username"] or f"user{row['user_id']}"
        lines.append(f"{i}. @{name} — {row['coins']} coins")
    text = "🏆 <b>Top players</b>\n\n" + ("\n".join(lines) if lines else "No players yet.")
    await message.answer(text)


async def main():
    db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
