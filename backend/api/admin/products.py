"""관리자 - 제휴 상품 관리 API"""
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AffiliateProduct, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/products", tags=["admin-products"])


@router.get("")
async def list_products(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(AffiliateProduct).order_by(AffiliateProduct.created_at.desc()))
    products = result.scalars().all()
    return {"items": [_fmt(p) for p in products]}


class ProductBody(BaseModel):
    name: str
    description: str | None = None
    url: str
    platform: str
    tags: list[str] = []
    category: str
    is_active: bool = True


@router.post("")
async def create_product(
    body: ProductBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    p = AffiliateProduct(
        name=body.name, description=body.description, url=body.url,
        platform=body.platform, tags=json.dumps(body.tags, ensure_ascii=False),
        category=body.category, is_active=body.is_active,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return _fmt(p)


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    body: ProductBody,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(AffiliateProduct).where(AffiliateProduct.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        from fastapi import HTTPException; raise HTTPException(404, "상품 없음")
    p.name = body.name; p.description = body.description; p.url = body.url
    p.platform = body.platform; p.tags = json.dumps(body.tags, ensure_ascii=False)
    p.category = body.category; p.is_active = body.is_active
    await session.commit()
    return _fmt(p)


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(AffiliateProduct).where(AffiliateProduct.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        from fastapi import HTTPException; raise HTTPException(404, "상품 없음")
    await session.delete(p)
    await session.commit()
    return {"ok": True}


def _fmt(p: AffiliateProduct) -> dict:
    tags = []
    try: tags = json.loads(p.tags or "[]")
    except Exception: pass
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "url": p.url, "platform": p.platform, "tags": tags,
        "category": p.category, "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
