"""
api.py
HTTP API used by the Telegram Mini App (webapp/index.html) to read/spend
coins. Every request carries Telegram's `initData`, which we verify with
telegram_auth.validate_init_data before touching the database — this is
what stops someone from editing client JS to grant themselves coins.

Run with:  uvicorn api:app --host 0.0.0.0 --port 8000
Put this behind HTTPS (Telegram requires HTTPS for Mini App URLs).
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
import shop_catalog
from telegram_auth import validate_init_data, InvalidInitData

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

app = FastAPI(title="Ludo Mini App API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Telegram's in-app browser; tighten if you host elsewhere too
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


def _user_from_init_data(init_data: str) -> int:
    try:
        user = validate_init_data(init_data, BOT_TOKEN)
    except InvalidInitData as e:
        raise HTTPException(status_code=401, detail=f"invalid initData: {e}")
    return user["id"], user.get("username", "")


class InitDataBody(BaseModel):
    initData: str


class ShopBody(InitDataBody):
    cosmetic_id: str
    slot: str


class GameResultBody(InitDataBody):
    result: str  # "win" | "lose"


def _profile_payload(user_id: int):
    user = db.get_user(user_id)
    return {
        "coins": user["coins"],
        "referral_count": user["referral_count"],
        "owned": db.get_owned_cosmetics(user_id),
        "active": db.get_active_cosmetics(user_id),
        "catalog": shop_catalog.CATALOG,
    }


@app.post("/api/profile")
def profile(body: InitDataBody):
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    return _profile_payload(user_id)


@app.post("/api/daily")
def daily(body: InitDataBody):
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    ok, wait_left = db.try_claim_daily(user_id, amount=100)
    if not ok:
        raise HTTPException(status_code=429, detail=f"try again in {wait_left}s")
    return _profile_payload(user_id)


@app.post("/api/ad-reward")
def ad_reward(body: InitDataBody):
    """
    Called after the Adsgram (or any rewarded-ad SDK) onReward callback
    fires client-side. For production, prefer verifying via the ad
    network's server-to-server postback instead of trusting the client
    call alone — see README "Anti-cheat" section.
    """
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    ok, wait_left = db.try_claim_ad_reward(user_id, amount=50)
    if not ok:
        raise HTTPException(status_code=429, detail=f"try again in {wait_left}s")
    return _profile_payload(user_id)


@app.post("/api/game-result")
def game_result(body: GameResultBody):
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    amount = 50 if body.result == "win" else 10
    db.add_coins(user_id, amount)
    return _profile_payload(user_id)


@app.post("/api/shop/buy")
def shop_buy(body: ShopBody):
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    item = shop_catalog.find_item(body.slot, body.cosmetic_id)
    if not item:
        raise HTTPException(status_code=404, detail="unknown cosmetic")
    if db.owns_cosmetic(user_id, body.cosmetic_id):
        raise HTTPException(status_code=400, detail="already owned")
    if not db.deduct_coins(user_id, item["price"]):
        raise HTTPException(status_code=402, detail="not enough coins")
    db.grant_cosmetic(user_id, body.cosmetic_id)
    return _profile_payload(user_id)


@app.post("/api/shop/equip")
def shop_equip(body: ShopBody):
    user_id, username = _user_from_init_data(body.initData)
    db.get_or_create_user(user_id, username)
    if body.cosmetic_id != "classic" and not db.owns_cosmetic(user_id, body.cosmetic_id):
        raise HTTPException(status_code=403, detail="not owned")
    db.set_active_cosmetic(user_id, body.slot, body.cosmetic_id)
    return _profile_payload(user_id)


@app.get("/api/leaderboard")
def leaderboard():
    return db.leaderboard(10)


# Serve the mini app itself at /
app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")
