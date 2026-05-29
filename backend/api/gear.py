"""용품 정보 라우터 — GET /api/gear"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Gear, get_session

router = APIRouter()


def _match_species(s_tags: list[str], species: str | None) -> bool:
    """어종 필터 매칭 로직.

    - species 없음/전체 → 전부 통과
    - species = 전어종   → 전어종 태그 상품만
    - species = 특정어종  → 해당 어종 태그 OR 전어종 태그
    """
    if not species or species == "전체":
        return True
    if species == "전어종":
        return "전어종" in s_tags
    return species in s_tags or "전어종" in s_tags


@router.get("/gear")
async def get_gear(
    species: str | None = None,
    level: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Gear))
    rows = result.scalars().all()

    items = []
    for g in rows:
        try:
            s_tags: list[str] = json.loads(g.species_tags or "[]")
            l_tags: list[str] = json.loads(g.level_tags or "[]")
        except (json.JSONDecodeError, TypeError):
            s_tags, l_tags = [], []

        if not _match_species(s_tags, species):
            continue
        if level and level not in l_tags:
            continue

        items.append({
            "id": g.id,
            "name": g.name,
            "species_tags": s_tags,
            "level_tags": l_tags,
            "guide": g.guide,
            "affiliate_url": g.affiliate_url,
            "affiliate_source": g.affiliate_source,
        })

    return {"species": species, "level": level, "items": items}
