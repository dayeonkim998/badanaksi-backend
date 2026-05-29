"""어종별 계절·해역 조황 조건 데이터.

season_score: 월별 기대 조황 지수 (0~100)
region_score: 해역별 서식 밀도 (0~100, 동해/서해/남해/제주)
water_temp_range: 적정 수온 범위 (min, max °C)
"""
from math import atan2, cos, radians, sin, sqrt

SPECIES_DATA: dict[str, dict] = {
    "참돔": {
        "water_temp_range": (17, 25),
        "season_score": {
            1: 30, 2: 35, 3: 50, 4: 70,
            5: 90, 6: 95, 7: 80, 8: 75,
            9: 90, 10: 85, 11: 60, 12: 40,
        },
        "region_score": {"동해": 60, "서해": 50, "남해": 95, "제주": 90},
    },
    "감성돔": {
        "water_temp_range": (15, 23),
        "season_score": {
            1: 50, 2: 55, 3: 65, 4: 75,
            5: 80, 6: 70, 7: 60, 8: 55,
            9: 70, 10: 85, 11: 80, 12: 65,
        },
        "region_score": {"동해": 55, "서해": 70, "남해": 90, "제주": 85},
    },
    "갈치": {
        "water_temp_range": (20, 28),
        "season_score": {
            1: 20, 2: 20, 3: 30, 4: 45,
            5: 60, 6: 75, 7: 90, 8: 95,
            9: 90, 10: 70, 11: 45, 12: 25,
        },
        "region_score": {"동해": 50, "서해": 65, "남해": 90, "제주": 95},
    },
    "방어": {
        "water_temp_range": (15, 25),
        "season_score": {
            1: 40, 2: 35, 3: 45, 4: 55,
            5: 65, 6: 60, 7: 50, 8: 50,
            9: 65, 10: 80, 11: 90, 12: 75,
        },
        "region_score": {"동해": 80, "서해": 50, "남해": 85, "제주": 95},
    },
    "볼락": {
        "water_temp_range": (10, 20),
        "season_score": {
            1: 80, 2: 85, 3: 90, 4: 85,
            5: 75, 6: 55, 7: 40, 8: 35,
            9: 50, 10: 65, 11: 75, 12: 80,
        },
        "region_score": {"동해": 85, "서해": 60, "남해": 80, "제주": 70},
    },
    "광어": {
        "water_temp_range": (14, 22),
        "season_score": {
            1: 60, 2: 65, 3: 70, 4: 75,
            5: 80, 6: 75, 7: 65, 8: 60,
            9: 70, 10: 75, 11: 70, 12: 65,
        },
        "region_score": {"동해": 75, "서해": 80, "남해": 80, "제주": 75},
    },
    "대구": {
        "water_temp_range": (5, 15),
        "season_score": {
            1: 90, 2: 85, 3: 70, 4: 50,
            5: 30, 6: 20, 7: 15, 8: 15,
            9: 25, 10: 45, 11: 65, 12: 80,
        },
        "region_score": {"동해": 90, "서해": 50, "남해": 60, "제주": 40},
    },
    "쭈꾸미": {
        "water_temp_range": (18, 26),
        "season_score": {
            1: 20, 2: 20, 3: 40, 4: 60,
            5: 70, 6: 65, 7: 55, 8: 50,
            9: 80, 10: 90, 11: 60, 12: 30,
        },
        "region_score": {"동해": 55, "서해": 90, "남해": 75, "제주": 65},
    },
    "오징어": {
        "water_temp_range": (16, 24),
        "season_score": {
            1: 30, 2: 25, 3: 35, 4: 50,
            5: 65, 6: 75, 7: 85, 8: 90,
            9: 85, 10: 70, 11: 55, 12: 40,
        },
        "region_score": {"동해": 90, "서해": 50, "남해": 70, "제주": 75},
    },
    "문어": {
        "water_temp_range": (15, 25),
        "season_score": {
            1: 30, 2: 30, 3: 45, 4: 60,
            5: 70, 6: 80, 7: 90, 8: 85,
            9: 75, 10: 65, 11: 50, 12: 40,
        },
        "region_score": {"동해": 70, "서해": 75, "남해": 85, "제주": 90},
    },
}


def get_sea_region(lat: float, lng: float) -> str:
    """위경도 → 해역명 (동해/서해/남해/제주)"""
    if lat < 34.0 and 125.0 <= lng <= 128.5:
        return "제주"
    if lng >= 129.0:
        return "동해"
    if lng <= 126.5:
        return "서해"
    return "남해"


def calculate_probability(
    species: str,
    month: int,
    sea_region: str,
    water_temp: float | None = None,
) -> int:
    """어종별 조황 확률 계산 (0~100).

    season_score 55% + region_score 45% 가중 합산.
    수온이 있으면 적정 범위 여부로 ±15~30% 보정.
    """
    if species not in SPECIES_DATA:
        return 0

    data = SPECIES_DATA[species]
    season = data["season_score"].get(month, 50)
    region = data["region_score"].get(sea_region, 50)
    base = season * 0.55 + region * 0.45

    if water_temp is not None:
        lo, hi = data["water_temp_range"]
        if lo <= water_temp <= hi:
            modifier = 1.15
        elif (lo - 5) <= water_temp < lo or hi < water_temp <= (hi + 5):
            modifier = 0.90
        else:
            modifier = 0.70
        base *= modifier

    return min(100, max(0, round(base)))


def _build_reason(
    species: str,
    month: int,
    sea_region: str,
    water_temp: float | None,
) -> list[str]:
    """확률 근거 문구 생성."""
    data = SPECIES_DATA[species]
    reasons: list[str] = []
    if data["season_score"].get(month, 0) >= 75:
        reasons.append(f"{month}월 최성기")
    if data["region_score"].get(sea_region, 0) >= 80:
        reasons.append(f"{sea_region} 주요 어종")
    if water_temp is not None:
        lo, hi = data["water_temp_range"]
        if lo <= water_temp <= hi:
            reasons.append(f"수온 {water_temp}°C 적정")
    return reasons


def get_all_probabilities(
    month: int,
    sea_region: str,
    water_temp: float | None = None,
) -> list[dict]:
    """전 어종 확률을 내림차순으로 반환."""
    result = []
    for species in SPECIES_DATA:
        prob = calculate_probability(species, month, sea_region, water_temp)
        reasons = _build_reason(species, month, sea_region, water_temp)
        result.append({"species": species, "probability": prob, "reasons": reasons})
    result.sort(key=lambda x: x["probability"], reverse=True)
    return result
