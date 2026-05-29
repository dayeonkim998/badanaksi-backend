"""항구·방파제·낚시 포인트 API
GET /api/spots?lat=&lng=&radius=30
harbors.py 정적 DB + Overpass API 결과 합산, 거리순 정렬
"""
import math
import time

import httpx
from fastapi import APIRouter

router = APIRouter()
_cache: dict = {}
_TTL = 6 * 3600  # 6시간

_OVERPASS = "https://overpass-api.de/api/interpreter"
_QUERY = """[out:json][timeout:15];
(
  node["harbour"](around:{radius_m},{lat},{lng});
  node["leisure"="fishing"](around:{radius_m},{lat},{lng});
  way["man_made"="breakwater"](around:{radius_m},{lat},{lng});
);
out center;"""


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    r = math.pi / 180
    dlat = (lat2 - lat1) * r
    dlng = (lng2 - lng1) * r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _classify(tags: dict) -> str:
    if tags.get("leisure") == "fishing":
        return "fishing"
    if tags.get("man_made") == "breakwater":
        return "breakwater"
    return "harbour"


@router.get("/spots")
async def get_spots(lat: float, lng: float, radius: int = 30):
    from data.harbors import HARBORS

    key = f"{round(lat, 2)}_{round(lng, 2)}_{radius}"
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _TTL:
        return _cache[key]["data"]

    spots: list[dict] = []

    # ── 1. 정적 DB 필터 ─────────────────────────────────────────────────────
    for h in HARBORS:
        dist = _haversine(lat, lng, h["lat"], h["lng"])
        if dist <= radius:
            spots.append({
                "id":          h["id"],
                "name":        h["name"],
                "type":        h.get("type", "harbour"),
                "region":      h.get("region", ""),
                "lat":         h["lat"],
                "lng":         h["lng"],
                "distance":    round(dist, 1),
                "address":     h.get("address", ""),
                "species":     h.get("species", []),
                "description": h.get("description", ""),
            })

    # ── 2. Overpass API (실패해도 정적 DB 결과 반환) ──────────────────────
    try:
        query = _QUERY.format(lat=lat, lng=lng, radius_m=radius * 1000)
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(_OVERPASS, data={"data": query})
            r.raise_for_status()
        seen: set[str] = set()
        for el in r.json().get("elements", []):
            tags = el.get("tags", {})
            if el.get("type") == "way":
                c = el.get("center", {})
                elat, elng = c.get("lat"), c.get("lon")
            else:
                elat, elng = el.get("lat"), el.get("lon")
            if not elat or not elng:
                continue
            uid = f"{round(elat, 3)}_{round(elng, 3)}"
            if uid in seen:
                continue
            seen.add(uid)
            stype = _classify(tags)
            name = (
                tags.get("name")
                or tags.get("seamark:name")
                or tags.get("name:ko")
            )
            # 이름 없는 unnamed 방파제·항구 skip
            if not name:
                continue
            dist = _haversine(lat, lng, elat, elng)
            spots.append({
                "id":          f"osm_{uid}",
                "name":        name,
                "type":        stype,
                "region":      "",
                "lat":         elat,
                "lng":         elng,
                "distance":    round(dist, 1),
                "address":     "",
                "species":     [],
                "description": "",
            })
            if len(spots) >= 100:
                break
    except Exception:
        pass

    spots.sort(key=lambda s: s["distance"])
    result = {"spots": spots[:60], "total": len(spots), "is_mock": False}
    _cache[key] = {"ts": now, "data": result}
    return result
