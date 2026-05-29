"""날씨·물때 통합 라우터 — 현재·시간별·조석·일출 종합 응답"""
import asyncio
import math
from datetime import datetime

from fastapi import APIRouter

from skills.weather_fetcher.fetch_weather import fetch_weather
from skills.weather_fetcher.fetch_tide import fetch_tide, _NEW_MOON_REF, _LUNAR_MONTH

router = APIRouter()


# ─── 내부 유틸 ────────────────────────────────────────────────────────────────

def _th(t: str) -> float:
    h, m = t.split(":")
    return int(h) + int(m) / 60


def _fmt(h: float) -> str:
    hh = int(h) % 24
    mm = int(round((h - int(h)) * 60)) % 60
    return f"{hh:02d}:{mm:02d}"


def _deg_dir(deg: float) -> str:
    dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return dirs[round(float(deg) / 45) % 8]


def _interpolate_tide(hour_f: float, events: list[dict]) -> int:
    """고조·저조 사이 코사인 보간으로 조위(cm) 추정"""
    if not events:
        return 50
    evts = sorted(events, key=lambda e: _th(e["time"]))
    for i in range(len(evts) - 1):
        t1, t2 = _th(evts[i]["time"]), _th(evts[i + 1]["time"])
        if t1 <= hour_f <= t2:
            h1, h2 = evts[i]["height"], evts[i + 1]["height"]
            frac = (hour_f - t1) / (t2 - t1)
            return round(h1 + (h2 - h1) * (1 - math.cos(math.pi * frac)) / 2)
    return evts[0]["height"] if hour_f < _th(evts[0]["time"]) else evts[-1]["height"]


_WIND_DIR_BONUS: dict[str, int] = {
    "북": 5, "북동": 5, "북서": 5,
    "남": -5, "남서": -5, "남동": -5,
    "동": 0, "서": 0,
}


def _fishing_score(
    wave: float,
    wind: float,
    tide_number: int = 5,
    wind_dir: str = "북",
) -> int:
    s = 50
    # 파고
    if wave <= 0.3:      s += 20
    elif wave <= 0.7:    s += 10
    elif wave <= 1.0:    s += 0
    elif wave <= 1.5:    s -= 15
    elif wave <= 2.0:    s -= 30
    else:                s -= 50
    # 풍속
    if wind <= 2:        s += 20
    elif wind <= 4:      s += 10
    elif wind <= 6:      s += 0
    elif wind <= 9:      s -= 15
    elif wind <= 12:     s -= 30
    else:                s -= 50
    # 물때
    if tide_number in (1, 2, 3, 13, 14, 15):  s += 15
    elif tide_number in (4, 5, 11, 12):        s += 5
    elif tide_number in (6, 7):                s += 0
    elif tide_number in (8, 9):                s -= 10
    elif tide_number == 10:                    s -= 5
    # 바람 방향 (육풍/해풍)
    s += _WIND_DIR_BONUS.get(wind_dir, 0)
    return max(0, min(100, s))


def _fishing_grade(score: int) -> str:
    if score >= 85:   return "최적"
    elif score >= 70: return "좋음"
    elif score >= 55: return "보통"
    elif score >= 40: return "나쁨"
    return "출조불가"


def _best_window(hourly: list[dict]) -> str:
    best_s = best_e = None
    best_n = cur_n = 0
    cur_start: str | None = None
    for h in hourly:
        if h["fishing_grade"] in ("최적", "좋음"):
            if cur_start is None:
                cur_start = h["time"]
            cur_n += 1
            if cur_n > best_n:
                best_n = cur_n
                best_s = cur_start
                best_e = h["time"]
        else:
            cur_start = None
            cur_n = 0
    if best_s and best_e:
        return f"오늘 낚시 최적 시간: {best_s} ~ {best_e}"
    return "오늘 낚시 좋은 시간대가 없습니다"


def _moon_times(lat: float, now: datetime) -> tuple[str, str]:
    elapsed = (now - _NEW_MOON_REF).total_seconds() / 86400
    age     = elapsed % _LUNAR_MONTH
    dy = (now - datetime(now.year, 1, 1)).days
    decl = 23.45 * math.sin(((360 / 365) * (dy - 81)) * math.pi / 180)
    cos_ha = -math.tan(lat * math.pi / 180) * math.tan(decl * math.pi / 180)
    ha = math.acos(max(-1.0, min(1.0, cos_ha))) * 180 / math.pi
    sr_h = 12 - ha / 15
    mr_h = (sr_h + (age / _LUNAR_MONTH) * 24) % 24
    return _fmt(mr_h), _fmt((mr_h + 12.4) % 24)


# ─── 라우터 ────────────────────────────────────────────────────────────────────

@router.get("/weather")
async def get_weather(lat: float, lng: float, date: str | None = None):
    now = datetime.now()

    # 병렬 조회
    weather_raw, tide_raw = await asyncio.gather(
        fetch_weather(lat, lng, date),
        fetch_tide(lat, lng, now),
        return_exceptions=True,
    )
    if isinstance(weather_raw, Exception): weather_raw = {}
    if isinstance(tide_raw,    Exception): tide_raw    = {}

    # 수온 (ocean 스킬, 실패 허용)
    sea_temp: float | None = None
    try:
        from skills.ocean_fetcher.fetch_fishing_ground import fetch_fishing_ground
        oc = await fetch_fishing_ground(lat, lng)
        sea_temp = oc.get("water_temp")
    except Exception:
        pass

    wd = weather_raw.get("weather", {})

    # ── current ────────────────────────────────────────────────────────────────
    current = {
        "temp":             wd.get("temp", 18),
        "feels_like":       wd.get("feels_like", wd.get("temp", 16)),
        "wind_speed":       wd.get("wind_speed", 3.5),
        "wind_direction":   _deg_dir(wd.get("wind_direction_deg", 180)),
        "wave_height":      wd.get("wave_height", 0.5),
        "weather_code":     wd.get("weather_code", 0),
        "weather_desc":     wd.get("condition", "맑음"),
        "precipitation_prob": wd.get("precipitation_prob", 0),
        "uv_index":         wd.get("uv_index", 3),
        "sea_temp":         sea_temp,
        "visibility":       "양호",
    }

    # ── tide ───────────────────────────────────────────────────────────────────
    today_events = tide_raw.get("today", [])
    tide_name    = tide_raw.get("tide_name",   "5물")
    tide_number  = tide_raw.get("tide_number",  5)

    now_h        = now.hour + now.minute / 60
    high_events  = [e for e in today_events if e["type"] == "고조"]
    future_highs = [e for e in high_events if _th(e["time"]) >= now_h]
    next_high    = (future_highs or high_events or [None])[0]

    fs = fe = None
    if next_high:
        nh = _th(next_high["time"])
        fs, fe = _fmt(nh - 1), _fmt(nh + 1)

    tide_section = {
        "tide_name":    tide_name,
        "tide_number":  tide_number,
        "today":        today_events,
        "next_high":    next_high,
        "feeding_start": fs,
        "feeding_end":   fe,
        "obs_name":     tide_raw.get("obs_name", ""),
    }

    wind_dir_str = current["wind_direction"]  # 이미 한글 방향 ("북서" 등)

    # ── hourly (24개, 조위 보간 + 낚시지수) ───────────────────────────────────
    raw_hourly = weather_raw.get("hourly", [])
    hourly: list[dict] = []
    for h in raw_hourly:
        hour_f = _th(h["time"])
        wave   = float(h.get("wave_height", current["wave_height"]))
        wind   = float(h.get("wind_speed",  current["wind_speed"]))
        h_wind_dir = h.get("wind_direction", wind_dir_str)
        score  = _fishing_score(wave, wind, tide_number, h_wind_dir)
        hourly.append({
            "time":          h["time"],
            "temp":          h.get("temp", current["temp"]),
            "wind_speed":    round(wind, 1),
            "wind_direction": h_wind_dir,
            "wave_height":   round(wave, 2),
            "weather_code":  h.get("weather_code", current["weather_code"]),
            "weather_desc":  h.get("weather_desc", current["weather_desc"]),
            "precip_prob":   h.get("precip_prob", 0),
            "tide_level":    _interpolate_tide(hour_f, today_events),
            "fishing_score": score,
            "fishing_grade": _fishing_grade(score),
        })

    best_fishing = _best_window(hourly)

    # ── sun/moon ───────────────────────────────────────────────────────────────
    moonrise, moonset = _moon_times(lat, now)
    sun = {
        "sunrise":  weather_raw.get("sunrise", "05:30"),
        "sunset":   weather_raw.get("sunset",  "19:40"),
        "moonrise": moonrise,
        "moonset":  moonset,
    }

    # ── suitability ────────────────────────────────────────────────────────────
    wave = current["wave_height"]
    wind = current["wind_speed"]
    suit_score = _fishing_score(wave, wind, tide_number, wind_dir_str)
    suit_grade = _fishing_grade(suit_score)
    _SUIT_ICON = {"최적": "🟢", "좋음": "🟢", "보통": "🟡", "나쁨": "🟠", "출조불가": "⛔"}
    suit = {
        "grade": suit_grade,
        "score": suit_score,
        "icon":  _SUIT_ICON.get(suit_grade, "🟡"),
        "reason": f"파고 {wave}m · 풍속 {wind}m/s({wind_dir_str}) · {tide_name}",
    }

    return {
        "location":     {"lat": lat, "lng": lng},
        "area":         weather_raw.get("area", ""),
        "current":      current,
        "tide":         tide_section,
        "hourly":       hourly,
        "sun":          sun,
        "best_fishing": best_fishing,
        "suitability":  suit,
        # 하위 호환 (기존 프론트엔드 코드 유지)
        "weather": {
            "wind_speed":  current["wind_speed"],
            "wave_height": current["wave_height"],
            "temp":        current["temp"],
            "condition":   current["weather_desc"],
        },
    }
