"""
FinShield - Auth Routes
POST /api/v1/auth/register  → create account
POST /api/v1/auth/login     → login → JWT
GET  /api/v1/auth/me        → current user info
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.user import UserRegister, UserLogin, UserResponse, Token
from services.auth_service import register_user, login_user, create_token, get_user_from_token
from utils.logger import get_structured_logger

router = APIRouter()
logger = get_structured_logger("finshield.auth.routes")
bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_user_from_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("/register", response_model=Token, status_code=201)
async def register(payload: UserRegister):
    try:
        user = register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name or payload.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = create_token(user["user_id"])
    return Token(
        access_token=token, token_type="bearer",
        user=UserResponse(**{k: v for k, v in user.items() if k != "password_hash"})
    )


@router.post("/login", response_model=Token)
async def login(payload: UserLogin):
    user = login_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["user_id"])
    return Token(
        access_token=token, token_type="bearer",
        user=UserResponse(**{k: v for k, v in user.items() if k != "password_hash"})
    )


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(current_user)):
    return UserResponse(**{k: v for k, v in user.items() if k != "password_hash"})
