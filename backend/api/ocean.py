"""해양 수온·어장 정보 라우터 — GET /api/ocean"""
import asyncio

from fastapi import APIRouter

from skills.ocean_fetcher.fetch_coastal_obs import fetch_coastal_data
from skills.ocean_fetcher.fetch_fishing_ground import fetch_nearest_water_temp

router = APIRouter()

# 어종별 적정 수온 범위 (°C)
_SPECIES_TEMP: dict[str, tuple[float, float]] = {
    "참돔":  (17, 25),
    "볼락":  (10, 20),
    "방어":  (15, 25),
    "농어":  (14, 24),
    "갈치":  (18, 26),
    "오징어": (14, 22),
    "고등어": (15, 23),
}


def _fishing_suitability(water_temp: float | None) -> dict:
    if water_temp is None:
        return {"grade": "정보없음", "reason": "수온 데이터를 가져올 수 없습니다", "species": []}

    matching = [sp for sp, (lo, hi) in _SPECIES_TEMP.items() if lo <= water_temp <= hi]

    if len(matching) >= 4:
        grade = "최상"
    elif len(matching) >= 2:
        grade = "상"
    elif len(matching) >= 1:
        grade = "중"
    else:
        grade = "하"

    species_str = ", ".join(matching[:3]) if matching else "적합 어종 없음"
    return {
        "grade": grade,
        "reason": f"수온 {water_temp}°C — {species_str}",
        "species": matching[:3],
    }


@router.get("/ocean")
async def get_ocean(lat: float, lng: float):
    fishing_result, coastal_result = await asyncio.gather(
        fetch_nearest_water_temp(lat, lng),
        fetch_coastal_data(lat, lng),
        return_exceptions=True,
    )

    if isinstance(fishing_result, Exception):
        fishing_result = {}
    if isinstance(coastal_result, Exception):
        coastal_result = {}

    water_temp = fishing_result.get("water_temp")
    suitability = _fishing_suitability(water_temp)

    return {
        "location": {"lat": lat, "lng": lng},
        "ocean": {
            "water_temp": water_temp,
            "salinity": coastal_result.get("salinity"),
            "dissolved_oxygen": coastal_result.get("dissolved_oxygen"),
            "ph": coastal_result.get("ph"),
            "air_temp": coastal_result.get("air_temp"),
        },
        "station": {
            "name": fishing_result.get("station_name") or coastal_result.get("station_name"),
            "distance_km": fishing_result.get("distance_km"),
            "region": coastal_result.get("region"),
            "observed_at": fishing_result.get("observed_at") or coastal_result.get("observed_at"),
        },
        "fishing_suitability": suitability,
        "is_mock": fishing_result.get("is_mock", False) or coastal_result.get("is_mock", False),
    }
