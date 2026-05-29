"""추천 라우터 — GET /api/recommend"""
from datetime import datetime

from fastapi import APIRouter

from skills.recommendation.species_conditions import (
    get_all_probabilities,
    get_sea_region,
)

router = APIRouter()

# ── 낚시 적합도 알고리즘 (weather.py 와 동일 기준) ──────────────────
_WIND_DIR_BONUS: dict[str, int] = {
    "북": 5, "북동": 5, "북서": 5,
    "남": -5, "남서": -5, "남동": -5,
    "동": 0, "서": 0,
}


def _fishing_score(
    wave: float = 0.5,
    wind: float = 3.0,
    tide_number: int = 5,
    wind_dir: str = "북",
) -> int:
    s = 50
    if wave <= 0.3:                              s += 20
    elif wave <= 0.7:                            s += 10
    elif wave <= 1.0:                            s += 0
    elif wave <= 1.5:                            s -= 15
    elif wave <= 2.0:                            s -= 30
    else:                                        s -= 50
    if wind <= 2:                                s += 20
    elif wind <= 4:                              s += 10
    elif wind <= 6:                              s += 0
    elif wind <= 9:                              s -= 15
    elif wind <= 12:                             s -= 30
    else:                                        s -= 50
    if tide_number in (1, 2, 3, 13, 14, 15):    s += 15
    elif tide_number in (4, 5, 11, 12):          s += 5
    elif tide_number in (8, 9):                  s -= 10
    elif tide_number == 10:                      s -= 5
    s += _WIND_DIR_BONUS.get(wind_dir, 0)
    return max(0, min(100, s))


def _fishing_grade(score: int) -> str:
    if score >= 85:   return "최적"
    elif score >= 70: return "좋음"
    elif score >= 55: return "보통"
    elif score >= 40: return "나쁨"
    return "출조불가"


# 고정 낚시 포인트 (반경 검색·마커용)
FISHING_SPOTS = [
    {"name": "완도",      "lat": 34.31, "lng": 126.75, "species": ["참돔", "감성돔"]},
    {"name": "통영",      "lat": 34.85, "lng": 128.43, "species": ["참돔", "갈치"]},
    {"name": "여수",      "lat": 34.74, "lng": 127.74, "species": ["감성돔", "볼락"]},
    {"name": "제주 서귀포", "lat": 33.25, "lng": 126.56, "species": ["방어", "참돔"]},
    {"name": "부산 기장", "lat": 35.24, "lng": 129.22, "species": ["감성돔", "우럭"]},
    {"name": "거제",      "lat": 34.88, "lng": 128.62, "species": ["참돔", "갈치"]},
    {"name": "포항 구룡포", "lat": 35.98, "lng": 129.55, "species": ["대구", "우럭"]},
    {"name": "목포",      "lat": 34.81, "lng": 126.39, "species": ["광어", "농어"]},
    {"name": "태안",      "lat": 36.74, "lng": 126.29, "species": ["광어", "우럭"]},
    {"name": "속초",      "lat": 38.20, "lng": 128.59, "species": ["가자미", "오징어"]},
]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt
    R = 6371.0
    la1, lo1, la2, lo2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat, dlng = la2 - la1, lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _nearest_spots(lat: float, lng: float, radius_km: float = 30) -> list[dict]:
    result = []
    for spot in FISHING_SPOTS:
        dist = _haversine(lat, lng, spot["lat"], spot["lng"])
        if dist <= radius_km:
            result.append({**spot, "distance_km": round(dist, 1)})
    result.sort(key=lambda x: x["distance_km"])
    return result


_RIG_BY_LEVEL = {
    "beginner":     {"name": "외줄낚시",   "description": "초보자도 쉽게 할 수 있는 기본 채비"},
    "intermediate": {"name": "지깅 채비",  "description": "중층 공략에 효과적인 지깅 채비"},
    "advanced":     {"name": "타이라바",   "description": "참돔·방어 전용 고급 채비"},
}


@router.get("/recommend")
async def get_recommend(
    lat: float,
    lng: float,
    level: str = "beginner",
    water_temp: float | None = None,
    wave: float = 0.5,
    wind: float = 3.0,
    wind_dir: str = "북",
    tide_number: int = 5,
):
    month = datetime.now().month
    sea_region = get_sea_region(lat, lng)
    probabilities = get_all_probabilities(month, sea_region, water_temp)

    top_species = [p["species"] for p in probabilities[:3]]
    nearby = _nearest_spots(lat, lng)

    # 가까운 포인트가 없으면 방향 기반 임시 포인트 2개
    if not nearby:
        nearby = [
            {
                "name": f"{sea_region} 포인트",
                "lat": lat + 0.05, "lng": lng + 0.08,
                "species": top_species[:2], "distance_km": 12.5,
            },
            {
                "name": "연안 갯바위",
                "lat": lat - 0.02, "lng": lng + 0.03,
                "species": top_species[1:3], "distance_km": 3.2,
            },
        ]

    score = _fishing_score(wave, wind, tide_number, wind_dir)
    grade = _fishing_grade(score)

    return {
        "location":       {"lat": lat, "lng": lng},
        "sea_region":     sea_region,
        "level":          level,
        "points":         nearby[:5],
        "species":        top_species,
        "rig":            _RIG_BY_LEVEL.get(level, _RIG_BY_LEVEL["beginner"]),
        "probabilities":  probabilities[:7],
        "fishing_score":  score,
        "fishing_grade":  grade,
        "conditions":     {
            "wave": wave, "wind": wind,
            "wind_dir": wind_dir, "tide_number": tide_number,
        },
    }
