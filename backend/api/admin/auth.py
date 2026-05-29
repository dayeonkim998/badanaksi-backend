"""관리자 로그인 API"""
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_session
from api.admin.middleware import create_admin_token

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL",    "admin@badanaksi.app")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me_in_env")


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
async def admin_login(body: LoginBody, session: AsyncSession = Depends(get_session)):
    # 환경변수 어드민 계정
    if body.email != ADMIN_EMAIL or body.password != ADMIN_PASSWORD:
        # DB에서 is_admin 사용자 확인
        result = await session.execute(
            select(User).where(User.email == body.email, User.is_admin.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
        token = create_admin_token(user.email, user.id)
        return {"token": token, "email": user.email}

    # 환경변수 슈퍼어드민
    token = create_admin_token(ADMIN_EMAIL, "super-admin")
    return {"token": token, "email": ADMIN_EMAIL, "is_super": True}
