"""Autentifikatsiya bog'liqliklari: fermer (JWT), qurilma (token), ichki servis (bot)."""
import hmac

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token, hash_token
from app.db.models import Device, Farmer, Field
from app.db.session import get_db


async def current_farmer(authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)) -> Farmer:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization required")
    try:
        farmer_id = decode_access_token(authorization[7:])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token is invalid or expired")
    farmer = await db.get(Farmer, farmer_id)
    if farmer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return farmer


async def owned_field(field_id: int, farmer: Farmer, db: AsyncSession) -> Field:
    """IDOR himoyasi: boshqa fermerning dalasi — 404 (mavjudligini ham oshkor qilmaymiz)."""
    f = await db.get(Field, field_id)
    if f is None or f.farmer_id != farmer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return f


async def current_device(authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)) -> Device:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device token required")
    device = await db.scalar(select(Device).where(Device.token_hash == hash_token(authorization[7:])))
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device token")
    return device


async def internal_auth(x_internal_token: str = Header(default="")) -> None:
    expected = get_settings().internal_api_token
    if not expected or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")


def is_admin(farmer: Farmer) -> bool:
    return farmer.role == "admin" or farmer.telegram_id in get_settings().admin_ids
