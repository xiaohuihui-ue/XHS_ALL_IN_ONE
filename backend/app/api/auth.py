from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.email import send_password_reset_email
from backend.app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.app.core.config import get_settings
from backend.app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


def _serialize_user(user: User) -> dict:
    return {"id": user.id, "username": user.username}


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


@router.post("/register")
def register(credentials: RegisterCredentials, db: Session = Depends(get_db)):
    username = credentials.username.strip()
    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    if db.scalar(select(User).where(User.email == credentials.email)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user = User(username=username, email=credentials.email, password_hash=hash_password(credentials.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(credentials: LoginCredentials, db: Session = Depends(get_db)):
    username = credentials.username.strip()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return _token_response(user)


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if decoded.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, decoded["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post("/logout")
def logout():
    return {"status": "ok"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        settings = get_settings()
        if not settings.smtp_host:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="邮件服务未配置，请联系管理员。",
            )
        token = create_password_reset_token(user.id)
        reset_url = f"{settings.frontend_url}/reset-password?token={token}"
        try:
            send_password_reset_email(user.email, reset_url)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="邮件发送失败，请稍后重试。",
            )
    return {"detail": "如果该邮箱已注册，重置链接已发送至邮箱。"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    invalid_exc = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="重置链接无效或已过期",
    )
    try:
        decoded = decode_token(payload.token)
    except HTTPException:
        raise invalid_exc

    if decoded.get("token_type") != "password_reset":
        raise invalid_exc

    user = db.get(User, decoded["user_id"])
    if user is None:
        raise invalid_exc

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"detail": "密码已重置，请重新登录。"}
