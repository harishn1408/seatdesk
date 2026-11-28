"""Password hashing, JWT issuance/verification, and role dependencies."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from db import get_db
from models import User

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET") or "seatdesk-dev-secret-key-at-least-32-chars"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES") or "60")
JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt after enforcing the 72-byte limit."""
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored bcrypt hash safely."""
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    """Sign an HS256 JWT with string sub, role, and wall-clock UTC expiry."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "iat": now, "nbf": now, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode Bearer JWT and return the authenticated User ORM row."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: str):
    """Build a FastAPI dependency enforcing that the user has one of `roles`."""
    def _role_guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _role_guard
