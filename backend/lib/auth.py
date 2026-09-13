import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request

from lib.db import db
from models.auth import UserPublic, UserRole


SESSION_COOKIE = "lm_session"
SESSION_DAYS = 7


def hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, expected = encoded.split(":", 1)
    except ValueError:
        return False
    actual = hash_password(password, salt_hex).split(":", 1)[1]
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    await db.sessions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token_hash": token_hash(token),
        "created_at": now,
        "expires_at": now + timedelta(days=SESSION_DAYS),
    })
    return token


async def current_user(request: Request) -> UserPublic:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = await db.sessions.find_one({
        "token_hash": token_hash(token),
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"id": session["user_id"], "active": True}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Account unavailable")
    return UserPublic(**user)


def require_roles(*roles: UserRole):
    async def dependency(user: UserPublic = Depends(current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="This workspace does not have access to that action")
        return user
    return dependency


async def ensure_default_users() -> None:
    accounts = [
        ("admin-001", "admin@lmchecker.gov.in", "Meera Nair", "admin", "National", "Admin@123"),
        ("inspector-042", "inspector@lmchecker.gov.in", "Aditi Rao", "inspector", "Delhi NCR", "Inspector@123"),
        ("consumer-001", "consumer@example.in", "Arjun Verma", "consumer", "Delhi NCR", "Consumer@123"),
    ]
    for user_id, email, name, role, region, password in accounts:
        await db.users.update_one(
            {"id": user_id},
            {"$setOnInsert": {"id": user_id, "email": email, "name": name, "role": role, "region": region, "active": True, "password_hash": hash_password(password)}},
            upsert=True,
        )