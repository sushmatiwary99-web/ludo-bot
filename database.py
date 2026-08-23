"""
database.py
SQLite persistence layer for the Ludo bot economy:
users, coin balances, referrals, and owned/equipped cosmetics.

No real-money value anywhere: coins are earned via referrals, daily
bonuses, match results, and rewarded ads, and can only be spent on
in-app cosmetics. There is no withdraw / cash-out path by design.
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "ludo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    username     TEXT,
    coins        INTEGER NOT NULL DEFAULT 500,
    referred_by  INTEGER,
    referral_count INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL,
    last_ad_ts   INTEGER NOT NULL DEFAULT 0,
    last_daily_ts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cosmetics_owned (
    user_id      INTEGER NOT NULL,
    cosmetic_id  TEXT NOT NULL,
    acquired_at  INTEGER NOT NULL,
    UNIQUE(user_id, cosmetic_id)
);

CREATE TABLE IF NOT EXISTS active_cosmetic (
    user_id      INTEGER PRIMARY KEY,
    dice_skin    TEXT NOT NULL DEFAULT 'classic',
    board_theme  TEXT NOT NULL DEFAULT 'classic',
    token_skin   TEXT NOT NULL DEFAULT 'classic'
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def get_or_create_user(user_id: int, username: str = "", referred_by: int = None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return dict(row)
        now = int(time.time())
        conn.execute(
            "INSERT INTO users (user_id, username, coins, referred_by, created_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, username, 500, referred_by, now),
        )
        conn.execute(
            "INSERT INTO active_cosmetic (user_id) VALUES (?)", (user_id,)
        )
        if referred_by and referred_by != user_id:
            conn.execute(
                "UPDATE users SET coins = coins + 100, referral_count = referral_count + 1 "
                "WHERE user_id=?",
                (referred_by,),
            )
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row)


def get_user(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def add_coins(user_id: int, amount: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
        row = conn.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["coins"] if row else None


def deduct_coins(user_id: int, amount: int) -> bool:
    """Returns False if balance would go negative (no purchase made)."""
    with get_conn() as conn:
        row = conn.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row or row["coins"] < amount:
            return False
        conn.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (amount, user_id))
        return True


def try_claim_daily(user_id: int, amount: int, cooldown_sec: int = 20 * 3600):
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT last_daily_ts FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return False, 0
        if now - row["last_daily_ts"] < cooldown_sec:
            return False, cooldown_sec - (now - row["last_daily_ts"])
        conn.execute(
            "UPDATE users SET coins = coins + ?, last_daily_ts=? WHERE user_id=?",
            (amount, now, user_id),
        )
        return True, 0


def try_claim_ad_reward(user_id: int, amount: int, cooldown_sec: int = 60):
    """Simple client-trusted cooldown gate; see README for real anti-cheat notes."""
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT last_ad_ts FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return False, 0
        if now - row["last_ad_ts"] < cooldown_sec:
            return False, cooldown_sec - (now - row["last_ad_ts"])
        conn.execute(
            "UPDATE users SET coins = coins + ?, last_ad_ts=? WHERE user_id=?",
            (amount, now, user_id),
        )
        return True, 0


def owns_cosmetic(user_id: int, cosmetic_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM cosmetics_owned WHERE user_id=? AND cosmetic_id=?",
            (user_id, cosmetic_id),
        ).fetchone()
        return row is not None


def grant_cosmetic(user_id: int, cosmetic_id: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cosmetics_owned (user_id, cosmetic_id, acquired_at) "
            "VALUES (?,?,?)",
            (user_id, cosmetic_id, int(time.time())),
        )


def get_owned_cosmetics(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT cosmetic_id FROM cosmetics_owned WHERE user_id=?", (user_id,)
        ).fetchall()
        return [r["cosmetic_id"] for r in rows]


def set_active_cosmetic(user_id: int, slot: str, cosmetic_id: str):
    assert slot in ("dice_skin", "board_theme", "token_skin")
    with get_conn() as conn:
        conn.execute(
            f"UPDATE active_cosmetic SET {slot}=? WHERE user_id=?", (cosmetic_id, user_id)
        )


def get_active_cosmetics(user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT dice_skin, board_theme, token_skin FROM active_cosmetic WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else {"dice_skin": "classic", "board_theme": "classic", "token_skin": "classic"}


def leaderboard(limit: int = 10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, username, coins FROM users ORDER BY coins DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
