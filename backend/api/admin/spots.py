"""관리자 - 낚시 포인트 관리 API"""
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import FishingSpot, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/spots", tags=["admin-spots"])


@router.get("")
async def list_spots(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(FishingSpot).order_by(FishingSpot.created_at.desc()))
    spots = result.scalars().all()
    return {"items": [_fmt(s) for s in spots]}


class SpotBody(BaseModel):
    name: str
    lat: float
    lng: float
    description: str | None = None
    species_tags: list[str] = []
    features: list[str] = []
    water_depth_m: float | None = None
    bottom_type: str | None = None
    is_verified: bool = False


@router.post("")
async def create_spot(
    body: SpotBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    s = FishingSpot(
        name=body.name, lat=body.lat, lng=body.lng,
        description=body.description,
        species_tags=json.dumps(body.species_tags, ensure_ascii=False),
        features=json.dumps(body.features, ensure_ascii=False),
        water_depth_m=body.water_depth_m, bottom_type=body.bottom_type,
        is_verified=body.is_verified,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return _fmt(s)


@router.put("/{spot_id}")
async def update_spot(
    spot_id: str, body: SpotBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(FishingSpot).where(FishingSpot.id == spot_id))
    s = result.scalar_one_or_none()
    if not s:
        from fastapi import HTTPException; raise HTTPException(404, "포인트 없음")
    s.name = body.name; s.lat = body.lat; s.lng = body.lng
    s.description = body.description; s.is_verified = body.is_verified
    s.species_tags = json.dumps(body.species_tags, ensure_ascii=False)
    s.features = json.dumps(body.features, ensure_ascii=False)
    s.water_depth_m = body.water_depth_m; s.bottom_type = body.bottom_type
    await session.commit()
    return _fmt(s)


@router.delete("/{spot_id}")
async def delete_spot(
    spot_id: str,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(FishingSpot).where(FishingSpot.id == spot_id))
    s = result.scalar_one_or_none()
    if not s:
        from fastapi import HTTPException; raise HTTPException(404, "포인트 없음")
    await session.delete(s)
    await session.commit()
    return {"ok": True}


def _fmt(s: FishingSpot) -> dict:
    def parse(v):
        try: return json.loads(v or "[]")
        except: return []
    return {
        "id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng,
        "description": s.description, "species_tags": parse(s.species_tags),
        "features": parse(s.features), "water_depth_m": s.water_depth_m,
        "bottom_type": s.bottom_type, "is_verified": s.is_verified,
        "avg_rating": s.avg_rating,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
