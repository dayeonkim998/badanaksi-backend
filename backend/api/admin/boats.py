"""관리자 - 낚시배 관리 API"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Boat, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/boats", tags=["admin-boats"])


@router.get("")
async def list_boats(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Boat).order_by(Boat.created_at.desc()))
    boats = result.scalars().all()
    return {"items": [_fmt(b) for b in boats]}


class BoatBody(BaseModel):
    name: str
    region: str
    departure: str
    price_per_person: int | None = None
    contact: str | None = None
    booking_url: str


@router.post("")
async def create_boat(
    body: BoatBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    b = Boat(**body.model_dump())
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return _fmt(b)


@router.put("/{boat_id}")
async def update_boat(
    boat_id: str, body: BoatBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Boat).where(Boat.id == boat_id))
    b = result.scalar_one_or_none()
    if not b:
        from fastapi import HTTPException; raise HTTPException(404, "낚시배 없음")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    await session.commit()
    return _fmt(b)


@router.delete("/{boat_id}")
async def delete_boat(
    boat_id: str,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Boat).where(Boat.id == boat_id))
    b = result.scalar_one_or_none()
    if not b:
        from fastapi import HTTPException; raise HTTPException(404, "낚시배 없음")
    await session.delete(b)
    await session.commit()
    return {"ok": True}


def _fmt(b: Boat) -> dict:
    return {
        "id": b.id, "name": b.name, "region": b.region,
        "departure": b.departure, "price_per_person": b.price_per_person,
        "contact": b.contact, "booking_url": b.booking_url,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
