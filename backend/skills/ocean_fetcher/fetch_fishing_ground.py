"""국립수산과학원 실시간어장정보 API — 최근접 관측소 수온 반환.

URL: https://www.nifs.go.kr/OpenAPI_json?id=risaList&key={key}
갱신: 30분 / 캐시 TTL: 30분
"""
import os
from math import atan2, cos, radians, sin, sqrt

import httpx

from skills.ocean_fetcher import cache as _cache

_KEY = os.getenv("NIFS_FISHING_GROUND_API_KEY", "")
_URL = "https://www.nifs.go.kr/OpenAPI_json"
_TTL = 1800  # 30분

# API 키 미설정 시 반환할 mock 데이터 (관측소: 부산 기본)
_MOCK: dict = {
    "water_temp": 18.0,
    "station_name": "부산(mock)",
    "distance_km": 0.0,
    "observed_at": "",
    "is_mock": True,
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A", "-") else None
    except (TypeError, ValueError):
        return None


def _parse_items(data: dict) -> list[dict]:
    """여러 가능한 응답 구조 처리."""
    for key in ("risa_obs", "result", "data", "response", "items"):
        val = data.get(key)
        if isinstance(val, list) and val:
            return val
        if isinstance(val, dict):
            for sub in ("data", "items", "item"):
                inner = val.get(sub)
                if isinstance(inner, list) and inner:
                    return inner
    return []


async def fetch_nearest_water_temp(lat: float, lng: float) -> dict:
    if not _KEY:
        return dict(_MOCK)

    cache_key = "risa_list"
    cached = _cache.get(cache_key, _TTL)
    if cached is None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as cli:
                r = await cli.get(_URL, params={"id": "risaList", "key": _KEY})
                r.raise_for_status()
                cached = r.json()
            _cache.set(cache_key, cached)
        except Exception:
            return dict(_MOCK) | {"error": "API 호출 실패"}

    items = _parse_items(cached)
    if not items:
        return dict(_MOCK) | {"error": "데이터 없음"}

    best: dict | None = None
    best_dist = float("inf")

    for item in items:
        slat = _safe_float(item.get("lat") or item.get("obs_lat") or item.get("la"))
        slng = _safe_float(item.get("lon") or item.get("lng") or item.get("obs_lon") or item.get("lo"))
        if slat is None or slng is None:
            continue
        dist = _haversine(lat, lng, slat, slng)
        if dist < best_dist:
            best_dist = dist
            best = item

    if best is None:
        return dict(_MOCK) | {"error": "최근접 관측소 없음"}

    temp = _safe_float(
        best.get("sea_tmp") or best.get("water_temp") or best.get("tmp") or best.get("wtemp")
    )
    name = best.get("obs_sta_nm") or best.get("name") or best.get("sta_nm") or ""

    return {
        "water_temp": temp,
        "station_name": str(name),
        "distance_km": round(best_dist, 1),
        "observed_at": str(best.get("obs_date") or best.get("obs_datetime") or ""),
        "is_mock": False,
    }
