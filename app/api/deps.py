import hashlib
import hmac
import json
import urllib.parse

from fastapi import Header, HTTPException

from ..config import BOT_TOKEN


def validate_init_data(init_data: str) -> dict:
    """Проверка подписи Telegram Web App initData, возвращает user-объект."""
    try:
        pairs = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(401, "Bad init data")

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "No hash")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        raise HTTPException(401, "Invalid signature")

    try:
        return json.loads(pairs["user"])
    except (KeyError, json.JSONDecodeError):
        raise HTTPException(401, "No user in init data")


async def get_telegram_user(x_init_data: str = Header(alias="X-Init-Data")) -> dict:
    return validate_init_data(x_init_data)
