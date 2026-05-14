"""
FinShield - Auth Service
JWT authentication with bcrypt password hashing.
In production: JWT secret pulled from HashiCorp Vault.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from utils.logger import get_structured_logger

logger = get_structured_logger("finshield.auth")

SECRET_KEY = "finshield-jwt-super-secret-2024"   # In prod: os.getenv("JWT_SECRET") from Vault
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# In-memory stores
_users: dict[str, dict] = {}          # user_id  → user
_by_username: dict[str, str] = {}     # username → user_id
_by_email: dict[str, str] = {}        # email    → user_id


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def register_user(username: str, email: str, password: str, full_name: str = "") -> dict:
    if username.lower() in _by_username:
        raise ValueError("Username already taken")
    if email.lower() in _by_email:
        raise ValueError("Email already registered")

    user_id = str(uuid.uuid4())
    user = {
        "user_id":      user_id,
        "username":     username,
        "email":        email.lower(),
        "full_name":    full_name or username,
        "password_hash": hash_password(password),
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    _users[user_id] = user
    _by_username[username.lower()] = user_id
    _by_email[email.lower()] = user_id
    logger.info("User registered", extra={"user_id": user_id, "username": username})
    return user


def login_user(username_or_email: str, password: str) -> Optional[dict]:
    uid = _by_username.get(username_or_email.lower()) or _by_email.get(username_or_email.lower())
    if not uid:
        return None
    user = _users.get(uid)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    logger.info("User logged in", extra={"user_id": uid, "username": user["username"]})
    return user


def get_user_from_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        return _users.get(uid) if uid else None
    except JWTError:
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    return _users.get(user_id)
