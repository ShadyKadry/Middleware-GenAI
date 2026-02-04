import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(32)  # force new login after application restart # set later in env TODO
JWT_ALG = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))


def create_token(subject: str, role: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,          # user id as string
        "role": role,
        "type": token_type,      # "access" or "refresh"
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def set_auth_cookies(resp, access_token: str, refresh_token: str) -> None:
    # local dev: secure=False; in prod behind HTTPS set secure=True TODO
    resp.set_cookie(ACCESS_COOKIE, access_token, httponly=True, samesite="lax", secure=False, path="/")
    resp.set_cookie(REFRESH_COOKIE, refresh_token, httponly=True, samesite="lax", secure=False, path="/")


def clear_auth_cookies(resp) -> None:
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/")


def get_access_cookie(access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE)) -> str:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return access_token


def get_refresh_cookie(refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE)) -> str:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return refresh_token


def current_principal(token: str = Depends(get_access_cookie)) -> Dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload
