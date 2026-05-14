"""FinShield - User Models"""
from pydantic import BaseModel
from typing import Optional


class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str   # accepts username OR email
    password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: str
    created_at: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
