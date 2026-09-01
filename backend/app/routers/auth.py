from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    bearer_scheme,
    create_session,
    get_current_user,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)
from ..database import get_db
from ..models import User, UserCredential, UserPreference, UserSession
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = normalize_email(str(payload.email))
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=email, display_name=payload.display_name.strip())
    user.credential = UserCredential(password_hash=hash_password(payload.password))
    user.preferences = UserPreference()
    db.add(user)
    await db.flush()
    token, expires_at = await create_session(db, user)
    await db.commit()
    return AuthResponse(access_token=token, expires_at=expires_at, user=user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = normalize_email(str(payload.email))
    row = (
        await db.execute(
            select(User, UserCredential)
            .join(UserCredential, UserCredential.user_id == User.id)
            .where(User.email == email)
        )
    ).first()
    if not row or not verify_password(payload.password, row.UserCredential.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    token, expires_at = await create_session(db, row.User)
    await db.commit()
    return AuthResponse(access_token=token, expires_at=expires_at, user=row.User)


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    if credentials:
        await db.execute(
            delete(UserSession).where(
                UserSession.token_hash == hash_token(credentials.credentials)
            )
        )
        await db.commit()

