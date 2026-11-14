"""Telegram initData tekshiruvi, JWT va qurilma tokenlari."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import jwt

from app.core.config import get_settings


class InitDataError(ValueError):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age_sec: int) -> dict:
    """Telegram Mini App initData imzosini rasmiy algoritm bo'yicha tekshiradi.

    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
    """
    if not init_data or not bot_token:
        raise InitDataError("initData yoki bot token yo'q")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash topilmadi")
    # Eslatma: "signature" maydoni (Bot API 8.0+) ham data_check_string tarkibiga kiradi
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("imzo noto'g'ri")
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if max_age_sec and time.time() - auth_date > max_age_sec:
        raise InitDataError("initData eskirgan")
    user = json.loads(pairs.get("user", "{}") or "{}")
    if not user.get("id"):
        raise InitDataError("foydalanuvchi ma'lumoti yo'q")
    return user


def create_access_token(farmer_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(farmer_id), "iat": now, "exp": now + timedelta(hours=settings.jwt_ttl_hours)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    return int(payload["sub"])


def new_device_token() -> str:
    return "sa_" + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_id() -> str:
    return "esp32-" + secrets.token_hex(3)
