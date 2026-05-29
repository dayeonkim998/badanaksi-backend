"""국립수산과학원 연안정지관측 API — 염분·DO·pH 반환.

URL: https://www.nifs.go.kr/OpenAPI_json?id=cooList&key={key}&sdate={date}&edate={date}&gru_nam={region}
갱신: 일 1회 / 캐시 TTL: 60분
"""
import os
from datetime import datetime

import httpx

from skills.ocean_fetcher import cache as _cache

_KEY = os.getenv("NIFS_COASTAL_OBS_API_KEY", "")
_URL = "https://www.nifs.go.kr/OpenAPI_json"
_TTL = 3600  # 60분

_REGION_LABELS = {"E": "동해", "W": "서해", "S": "남해"}

_MOCK: dict = {
    "salinity": 33.2,
    "dissolved_oxygen": 7.8,
    "ph": 8.1,
    "air_temp": 19.0,
    "station_name": "완도(mock)",
    "observed_at": "",
    "region": "남해",
    "is_mock": True,
}


def _get_region(lng: float) -> str:
    if lng >= 129.0:
        return "E"
    if lng <= 126.5:
        return "W"
    return "S"


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A", "-") else None
    except (TypeError, ValueError):
        return None


def _parse_items(data: dict) -> list[dict]:
    for key in ("coo_obs", "result", "data", "response", "items"):
        val = data.get(key)
        if isinstance(val, list) and val:
            return val
        if isinstance(val, dict):
            for sub in ("data", "items", "item"):
                inner = val.get(sub)
                if isinstance(inner, list) and inner:
                    return inner
    return []


async def fetch_coastal_data(lat: float, lng: float) -> dict:
    if not _KEY:
        return dict(_MOCK)

    region = _get_region(lng)
    today = datetime.now().strftime("%Y%m%d")
    cache_key = f"coo_{region}_{today}"

    cached = _cache.get(cache_key, _TTL)
    if cached is None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as cli:
                r = await cli.get(_URL, params={
                    "id": "cooList",
                    "key": _KEY,
                    "sdate": today,
                    "edate": today,
                    "gru_nam": region,
                })
                r.raise_for_status()
                cached = r.json()
            _cache.set(cache_key, cached)
        except Exception:
            return dict(_MOCK) | {"error": "API 호출 실패"}

    items = _parse_items(cached)
    if not items:
        return dict(_MOCK) | {"error": "데이터 없음"}

    latest = items[-1]

    return {
        "salinity": _safe_float(latest.get("sal") or latest.get("salinity") or latest.get("salin")),
        "dissolved_oxygen": _safe_float(latest.get("do") or latest.get("dissolved_oxygen") or latest.get("dox")),
        "ph": _safe_float(latest.get("ph")),
        "air_temp": _safe_float(latest.get("air_tmp") or latest.get("air_temp") or latest.get("atemp")),
        "station_name": str(latest.get("coo_sta_nm") or latest.get("sta_nm") or latest.get("name") or ""),
        "observed_at": str(latest.get("obs_date") or latest.get("obs_datetime") or ""),
        "region": _REGION_LABELS.get(region, "남해"),
        "is_mock": False,
    }
