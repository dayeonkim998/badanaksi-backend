"""관리자 - 회원 관리 API"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
async def list_users(
    q: str | None = Query(None),
    page: int = 1,
    limit: int = 20,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(User).where(User.is_deleted.is_(False))
    if q:
        stmt = stmt.where(
            or_(User.nickname.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
        )
    total_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_result.scalar_one()
    stmt = stmt.offset((page - 1) * limit).limit(limit).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    users = result.scalars().all()
    return {
        "total": total, "page": page, "limit": limit,
        "items": [_fmt(u) for u in users],
    }


@router.get("/stats")
async def user_stats(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    total = (await session.execute(select(func.count(User.id)).where(User.is_deleted.is_(False)))).scalar_one()
    premium = (await session.execute(select(func.count(User.id)).where(User.plan == "premium", User.is_deleted.is_(False)))).scalar_one()
    today_dt = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = (await session.execute(select(func.count(User.id)).where(User.created_at >= today_dt))).scalar_one()
    return {"total": total, "premium": premium, "new_today": new_today}


class UserPatch(BaseModel):
    nickname: str | None = None
    plan: str | None = None
    is_admin: bool | None = None


@router.patch("/{user_id}")
async def patch_user(
    user_id: str,
    body: UserPatch,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(404, "회원을 찾을 수 없습니다")
    if body.nickname is not None: user.nickname = body.nickname
    if body.plan is not None:     user.plan = body.plan
    if body.is_admin is not None: user.is_admin = body.is_admin
    await session.commit()
    return _fmt(user)


@router.delete("/{user_id}")
async def soft_delete_user(
    user_id: str,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(404, "회원을 찾을 수 없습니다")
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    await session.commit()
    return {"ok": True}


def _fmt(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "nickname": u.nickname,
        "plan": u.plan, "is_admin": u.is_admin,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }
