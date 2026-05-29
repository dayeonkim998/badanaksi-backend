"""
조석예보 API (국립해양조사원 / 공공데이터포털) 연동
베이스 URL: https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService
실패 시 달(음력) 계산식 fallback
"""
import json
import logging
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent.parent / "output" / "tide_cache"
CACHE_TTL = 6 * 3600  # 6시간

BASE_URL = (
    "https://apis.data.go.kr/1192136/tideFcstHghLw"
    "/GetTideFcstHghLwApiService"
)

# ── 관측소 테이블 (API 실측 좌표 기준, DT_0009 제외 – 데이터 없음) ───────────
# high_spring: 대조 고조 평균(cm) / high_neap: 소조 고조 평균(cm)
STATIONS = [
    {"code": "DT_0001", "name": "인천",   "lat": 37.452, "lng": 126.592, "high_spring": 930, "high_neap": 540},
    {"code": "DT_0002", "name": "보령",   "lat": 36.967, "lng": 126.823, "high_spring": 880, "high_neap": 490},
    {"code": "DT_0003", "name": "군산",   "lat": 35.426, "lng": 126.421, "high_spring": 650, "high_neap": 360},
    {"code": "DT_0004", "name": "제주",   "lat": 33.528, "lng": 126.543, "high_spring": 275, "high_neap": 140},
    {"code": "DT_0005", "name": "부산",   "lat": 35.096, "lng": 129.035, "high_spring": 152, "high_neap":  80},
    {"code": "DT_0006", "name": "묵호",   "lat": 37.550, "lng": 129.116, "high_spring":  40, "high_neap":  20},
    {"code": "DT_0007", "name": "목포",   "lat": 34.780, "lng": 126.376, "high_spring": 480, "high_neap": 260},
    {"code": "DT_0008", "name": "안산",   "lat": 37.192, "lng": 126.647, "high_spring": 810, "high_neap": 450},
    {"code": "DT_0010", "name": "서귀포", "lat": 33.240, "lng": 126.562, "high_spring": 295, "high_neap": 150},
    {"code": "DT_0011", "name": "후포",   "lat": 36.678, "lng": 129.453, "high_spring":  35, "high_neap":  18},
]

# ── 음력 날짜 → (물때 이름, 물때 번호) ────────────────────────────────────────
# 기준: 1일=8물, 15일=한사리, 23일=8물, 30일=한사리
_TIDE_MAP: dict[int, tuple[str, int]] = {
     1: ("8물",    8),   2: ("7물",    7),   3: ("6물",    6),
     4: ("5물",    5),   5: ("4물",    4),   6: ("3물",    3),
     7: ("2물",    2),   8: ("1물",    1),   9: ("조금",   0),
    10: ("무시",   0),  11: ("1물",    1),  12: ("2물",    2),
    13: ("3물",    3),  14: ("4물",    4),  15: ("한사리", 15),
    16: ("9물",    9),  17: ("8물",    8),  18: ("7물",    7),
    19: ("6물",    6),  20: ("5물",    5),  21: ("4물",    4),
    22: ("3물",    3),  23: ("8물",    8),  24: ("조금",   0),
    25: ("무시",   0),  26: ("1물",    1),  27: ("2물",    2),
    28: ("3물",    3),  29: ("4물",    4),  30: ("한사리", 15),
}

_LUNAR_MONTH  = 29.53058867
_NEW_MOON_REF = datetime(2000, 1, 6, 18, 14)


# ─── 유틸 ────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _nearest_station(lat: float, lng: float) -> dict:
    return min(STATIONS, key=lambda s: _haversine_km(lat, lng, s["lat"], s["lng"]))


def _lunar_day(dt: datetime) -> int:
    elapsed = (dt - _NEW_MOON_REF).total_seconds() / 86400
    age = elapsed % _LUNAR_MONTH
    return min(int(age) + 1, 30)


def _tide_name(lunar_day: int) -> tuple[str, int]:
    return _TIDE_MAP.get(lunar_day, (f"{lunar_day}물", lunar_day))


# ─── API 응답 파싱 ────────────────────────────────────────────────────────────
# 응답 구조:
#   {"header": {"resultCode": "00"}, "body": {"items": {"item": [...]}}}
# item 필드:
#   predcDt      "2026-05-21 06:32"  (예보 시각)
#   predcTdlvVl  312.0               (조위 cm)
#   extrSe       "1" | "2" | "3" | "4"
#                1·3 = 고조,  2·4 = 저조

def _parse_new_items(items: list) -> list[dict]:
    """새 API 응답 파싱: predcDt / predcTdlvVl / extrSe"""
    result = []
    for item in items:
        se  = str(item.get("extrSe", "")).strip()
        dt  = str(item.get("predcDt", "")).strip()   # "YYYY-MM-DD HH:MM"
        lv  = item.get("predcTdlvVl", 0)

        if se in ("1", "3"):
            kind = "고조"
        elif se in ("2", "4"):
            kind = "저조"
        else:
            continue

        # "YYYY-MM-DD HH:MM" → "HH:MM"
        time_str = dt[-5:] if len(dt) >= 5 else dt

        try:
            height = int(float(lv))
        except (ValueError, TypeError):
            height = 0

        result.append({"type": kind, "time": time_str, "height": height})

    result.sort(key=lambda x: x["time"])
    return result


def _extract_items(data: dict) -> list:
    """JSON body에서 item 배열 추출"""
    # 형식: {"header": {...}, "body": {"items": {"item": [...]}}}
    body  = data.get("body", {})
    items = body.get("items", {})
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]  # 항목이 1개일 때 dict 로 오는 경우
    return items or []


# ─── API 호출 ────────────────────────────────────────────────────────────────

async def _call_api(obs_code: str, date_str: str) -> list[dict]:
    """
    파라미터: serviceKey(소문자), obsCode, date(YYYYMMDD), type=json
    """
    api_key = os.getenv("TIDE_API_KEY", "")
    if not api_key:
        raise ValueError("TIDE_API_KEY 미설정")

    params = {
        "serviceKey": api_key,
        "obsCode":    obs_code,
        "date":       date_str,
        "type":       "json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(BASE_URL, params=params)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}: {resp.text[:120]}")
        data = resp.json()

    # 오류 코드 확인
    result_code = data.get("header", {}).get("resultCode", "")
    if result_code != "00":
        msg = data.get("header", {}).get("resultMsg", "")
        raise ValueError(f"API 오류 {result_code}: {msg}")

    items = _extract_items(data)
    if not items:
        raise ValueError(f"빈 item 배열: {str(data)[:120]}")

    return _parse_new_items(items)


# ─── 달 계산 fallback ─────────────────────────────────────────────────────────

def _fallback_tide_times(dt: datetime, station: dict | None = None) -> list[dict]:
    """반일주조 기반 고조·저조 시각 + 관측소별 조차 추정"""
    elapsed = (dt - _NEW_MOON_REF).total_seconds() / 86400
    age     = elapsed % _LUNAR_MONTH
    period  = 12 + 25 / 60
    phase_delay = (age * 24 / _LUNAR_MONTH) % 24
    neap_ratio  = abs(math.sin(math.pi * age / (_LUNAR_MONTH / 2)))

    def fmt(h: float) -> str:
        hh = int(h) % 24
        mm = int(round((h - int(h)) * 60))
        if mm >= 60:
            hh = (hh + 1) % 24; mm = 0
        return f"{hh:02d}:{mm:02d}"

    if station:
        hi_s = station.get("high_spring", 300)
        hi_n = station.get("high_neap",   160)
        hi   = round(hi_n + (hi_s - hi_n) * neap_ratio)
        lo   = round(hi * 0.12)
    else:
        hi, lo = 280, 35

    h1 = phase_delay % 24
    l1 = (h1 + period / 2) % 24
    h2 = (h1 + period)     % 24
    l2 = (l1 + period)     % 24

    events = [
        {"type": "고조", "time": fmt(h1), "height": hi},
        {"type": "저조", "time": fmt(l1), "height": lo},
        {"type": "고조", "time": fmt(h2), "height": round(hi * 0.95)},
        {"type": "저조", "time": fmt(l2), "height": round(lo * 1.1)},
    ]
    events.sort(key=lambda x: x["time"])
    return events


# ─── 공개 API ─────────────────────────────────────────────────────────────────

async def fetch_tide(lat: float, lng: float, dt: datetime | None = None) -> dict:
    """
    조석예보 데이터 조회 (실 API → fallback 순).
    6시간 캐시.
    """
    now          = dt or datetime.now()
    today_str    = now.strftime("%Y%m%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y%m%d")

    station    = _nearest_station(lat, lng)
    cache_key  = f"{station['code']}_{today_str}"
    cache_path = CACHE_DIR / f"{cache_key}.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 유효 캐시 반환
    if cache_path.exists():
        age_s = now.timestamp() - cache_path.stat().st_mtime
        if age_s < CACHE_TTL:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    lunar_day  = _lunar_day(now)
    tide_name, tide_number = _tide_name(lunar_day)

    try:
        today_items    = await _call_api(station["code"], today_str)
        tomorrow_items = await _call_api(station["code"], tomorrow_str)
        is_fallback = False
        logger.info("조석 API 성공: %s %s (%d개)", station["name"], today_str, len(today_items))
    except Exception as exc:
        logger.warning("조석 API 실패 → fallback: %s", exc)
        today_items    = _fallback_tide_times(now, station)
        tomorrow_items = _fallback_tide_times(now + timedelta(days=1), station)
        is_fallback = True

    result = {
        "today":       today_items,
        "tomorrow":    tomorrow_items,
        "obs_name":    station["name"],
        "tide_name":   tide_name,
        "tide_number": tide_number,
        "lunar_day":   lunar_day,
        "is_fallback": is_fallback,
        "fetched_at":  now.isoformat(),
    }
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ─── /api/weather 하위 호환 래퍼 ─────────────────────────────────────────────

def calculate_tide(lat: float, lng: float, dt: datetime | None = None) -> dict:
    """weather.py 의 동기 호출용 래퍼 (fallback 값만 즉시 반환)."""
    now       = dt or datetime.now()
    lunar_day = _lunar_day(now)
    tide_name, _ = _tide_name(lunar_day)

    from .regions import get_sea_area, SEA_AREA_META
    area   = get_sea_area(lat, lng)
    offset = SEA_AREA_META.get(area, {}).get("tide_offset", 0)

    elapsed = (now - _NEW_MOON_REF).total_seconds() / 86400
    age = elapsed % _LUNAR_MONTH
    period = 12 + 25 / 60
    phase_delay = (age * 24 / _LUNAR_MONTH) % 24

    def fmt(h: float) -> str:
        hh = int(h) % 24
        mm = int(round((h - int(h)) * 60))
        if mm >= 60:
            hh = (hh + 1) % 24; mm = 0
        return f"{hh:02d}:{mm:02d}"

    high_h = (phase_delay + offset / 60) % 24
    low_h  = (high_h + period / 2)       % 24

    num = _TIDE_MAP.get(lunar_day, (tide_name, 5))[1]
    if num == 0:
        grade, reason = "상", f"{tide_name} — 조류 잠잠, 낚시 최적"
    elif num >= 10:
        grade, reason = "하", f"{tide_name} — 조류 강함"
    else:
        grade, reason = "중", f"{tide_name} — 조류 보통"

    return {
        "lunar_day": lunar_day,
        "type":      tide_name,
        "high":      fmt(high_h),
        "low":       fmt(low_h),
        "grade":     grade,
        "reason":    reason,
    }
