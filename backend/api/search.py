"""지역 검색 프록시 — Nominatim OpenStreetMap (CORS 우회)"""
import httpx
from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/search/location")
async def search_location(q: str = Query(..., min_length=1)):
    """
    한국 지역명 검색 → Nominatim 프록시.
    User-Agent 헤더 포함으로 Nominatim 이용정책 준수.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q.strip(),
                    "format": "json",
                    "countrycodes": "kr",
                    "limit": 5,
                    "accept-language": "ko",
                },
                headers={"User-Agent": "FishingPlatform/1.0 (https://github.com/fishing-platform)"},
            )
            resp.raise_for_status()
            data: list[dict] = resp.json()

        return [
            {
                "name":    p.get("display_name", "").split(",")[0].strip(),
                "lat":     float(p["lat"]),
                "lng":     float(p["lon"]),
                "display": ", ".join(p.get("display_name", "").split(",")[:3]).strip(),
            }
            for p in data
            if p.get("lat") and p.get("lon")
        ]
    except Exception:
        return []
