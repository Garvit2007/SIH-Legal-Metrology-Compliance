from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


UserRole = Literal["admin", "inspector", "consumer"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    region: str
    active: bool = True


class SessionDocument(BaseModel):
    id: str
    user_id: str
    token_hash: str
    created_at: datetime
    expires_at: datetime