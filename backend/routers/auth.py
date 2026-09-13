from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from lib.auth import SESSION_COOKIE, create_session, current_user, token_hash, verify_password
from lib.db import db
from models.auth import LoginRequest, UserPublic


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserPublic)
async def login(input: LoginRequest, response: Response) -> UserPublic:
    user = await db.users.find_one({"email": input.email.lower(), "active": True})
    if not user or not verify_password(input.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = await create_session(user["id"])
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return UserPublic(**user)


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(current_user)) -> UserPublic:
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.sessions.delete_many({"token_hash": token_hash(token)})
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.delete("/sessions/expired", status_code=204)
async def clear_expired(user: UserPublic = Depends(current_user)) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    await db.sessions.delete_many({"expires_at": {"$lte": datetime.now(timezone.utc)}})