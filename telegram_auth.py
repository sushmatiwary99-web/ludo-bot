"""
telegram_auth.py
Validates Telegram Mini App `initData` per Telegram's documented scheme:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Every API call from the webapp must pass initData, and we HMAC-verify it
server-side with the bot token before trusting the embedded user_id. This
stops anyone from calling the coin/shop endpoints with a forged user id.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age_sec: int = 86400) -> dict:
    """Returns the parsed `user` dict from initData if valid, else raises."""
    if not init_data:
        raise InvalidInitData("empty initData")

    pairs = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitData("hash mismatch")

    auth_date = int(pairs.get("auth_date", "0"))
    if max_age_sec and (time.time() - auth_date) > max_age_sec:
        raise InvalidInitData("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InvalidInitData("missing user")

    return json.loads(user_raw)
