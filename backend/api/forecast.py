"""날씨 예보 라우터
GET /api/weather/forecast  — 10일 예보
GET /api/weather/hourly    — 24시간 시간대별 예보
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter

from skills.weather_fetcher.fetch_tide import calculate_tide

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 시간대별 예보 캐시 ──
_HOURLY_CACHE: dict = {}
_HOURLY_TTL = 7200  # 2시간

WEATHER_CODE_ICON: dict[int, str] = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}

CACHE_DIR = Path(__file__).parent.parent.parent / "output" / "weather_cache"
CACHE_TTL = 10800  # 3시간

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

WEATHER_CODE_MAP: dict[int, str] = {
    0: "맑음", 1: "맑음", 2: "구름많음", 3: "흐림",
    45: "안개", 48: "안개",
    51: "이슬비", 53: "이슬비", 55: "이슬비",
    61: "비", 63: "비", 65: "비",
    71: "눈", 73: "눈", 75: "눈",
    80: "비", 81: "비", 82: "비",
    95: "천둥", 96: "천둥", 99: "천둥",
}

WIND_DIR_KO = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]


def _wind_dir(degrees: float | None) -> str:
    if degrees is None:
        return "-"
    return WIND_DIR_KO[round(degrees / 45) % 8]


_WIND_DIR_BONUS: dict[str, int] = {
    "북": 5, "북동": 5, "북서": 5,
    "남": -5, "남서": -5, "남동": -5,
    "동": 0, "서": 0,
}
_SUIT_ICON = {"최적": "🟢", "좋음": "🟢", "보통": "🟡", "나쁨": "🟠", "출조불가": "⛔"}


def _forecast_score(
    wave: float, wind: float, tide_lunar_day: int = 5, wind_dir: str = "북",
) -> int:
    s = 50
    if wave <= 0.3:                               s += 20
    elif wave <= 0.7:                             s += 10
    elif wave <= 1.0:                             s += 0
    elif wave <= 1.5:                             s -= 15
    elif wave <= 2.0:                             s -= 30
    else:                                         s -= 50
    if wind <= 2:                                 s += 20
    elif wind <= 4:                               s += 10
    elif wind <= 6:                               s += 0
    elif wind <= 9:                               s -= 15
    elif wind <= 12:                              s -= 30
    else:                                         s -= 50
    if tide_lunar_day in (1, 2, 3, 13, 14, 15):  s += 15
    elif tide_lunar_day in (4, 5, 11, 12):        s += 5
    elif tide_lunar_day in (8, 9):                s -= 10
    elif tide_lunar_day == 10:                    s -= 5
    s += _WIND_DIR_BONUS.get(wind_dir, 0)
    return max(0, min(100, s))


def _forecast_grade(score: int) -> str:
    if score >= 85:   return "최적"
    elif score >= 70: return "좋음"
    elif score >= 55: return "보통"
    elif score >= 40: return "나쁨"
    return "출조불가"


def _suitability(
    wave: float, wind: float, tide_lunar_day: int = 5, wind_dir: str = "북",
) -> dict:
    score = _forecast_score(wave, wind, tide_lunar_day, wind_dir)
    grade = _forecast_grade(score)
    return {
        "grade":  grade,
        "score":  score,
        "icon":   _SUIT_ICON.get(grade, "🟡"),
        "reason": f"파고 {wave}m · 풍속 {wind}m/s({wind_dir})",
    }


def _build_days(lat: float, lng: float, wd: dict, waves: list | None) -> list[dict]:
    days = []
    for i, date_str in enumerate(wd["time"]):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = WEEKDAYS[date.weekday()]
        code = int(wd["weather_code"][i] or 0)
        condition = WEATHER_CODE_MAP.get(code, "흐림")

        wave = round(float(waves[i]) if waves and waves[i] is not None else 0.5, 2)
        wind = round(float(wd["wind_speed_10m_max"][i] or 0.0), 1)
        temp_min = round(float(wd["temperature_2m_min"][i] or 0.0), 1)
        temp_max = round(float(wd["temperature_2m_max"][i] or 0.0), 1)
        app_min = round(float(wd.get("apparent_temperature_min", [None] * (i + 1))[i] or temp_min), 1)
        app_max = round(float(wd.get("apparent_temperature_max", [None] * (i + 1))[i] or temp_max), 1)
        wind_dir = _wind_dir(wd.get("wind_direction_10m_dominant", [None] * (i + 1))[i])

        tide = calculate_tide(lat, lng, date)
        suit = _suitability(wave, wind, tide.get("lunar_day", 5), wind_dir)

        days.append({
            "date": date_str,
            "weekday": weekday,
            "condition": condition,
            "weather_code": code,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "apparent_temp_min": app_min,
            "apparent_temp_max": app_max,
            "wave_height": wave,
            "wind_speed": wind,
            "wind_direction": wind_dir,
            "tide_name": tide["type"],
            "tide_lunar_day": tide["lunar_day"],
            "tide_high": tide["high"],
            "tide_low": tide["low"],
            "tide_grade": tide["grade"],
            "suitability": suit,
        })
    return days


async def _fetch_open_meteo(lat: float, lng: float) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        weather_fut = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lng,
                "daily": ",".join([
                    "temperature_2m_max", "temperature_2m_min",
                    "apparent_temperature_max", "apparent_temperature_min",
                    "wind_speed_10m_max", "wind_direction_10m_dominant",
                    "weather_code",
                ]),
                "wind_speed_unit": "ms",
                "timezone": "Asia/Seoul",
                "forecast_days": 10,
            },
        )
        marine_fut = client.get(
            "https://marine-api.open-meteo.com/v1/marine",
            params={
                "latitude": lat, "longitude": lng,
                "daily": "wave_height_max",
                "timezone": "Asia/Seoul",
                "forecast_days": 10,
            },
        )
        results = await asyncio.gather(weather_fut, marine_fut, return_exceptions=True)

    weather_resp, marine_resp = results
    if isinstance(weather_resp, Exception):
        raise weather_resp
    weather_resp.raise_for_status()
    wd = weather_resp.json()["daily"]

    waves = None
    if not isinstance(marine_resp, Exception):
        try:
            marine_resp.raise_for_status()
            waves = marine_resp.json()["daily"].get("wave_height_max")
        except Exception:
            pass

    return _build_days(lat, lng, wd, waves)


def _fallback_days(lat: float, lng: float) -> list[dict]:
    today = datetime.now()
    season_temp = {1: 5, 2: 7, 3: 12, 4: 17, 5: 21, 6: 24, 7: 27, 8: 28, 9: 23, 10: 18, 11: 12, 12: 7}
    base_temp = season_temp.get(today.month, 18)
    days = []
    for i in range(10):
        d = today + timedelta(days=i)
        tide = calculate_tide(lat, lng, d)
        days.append({
            "date": d.strftime("%Y-%m-%d"),
            "weekday": WEEKDAYS[d.weekday()],
            "condition": "맑음",
            "weather_code": 0,
            "temp_min": base_temp - 5,
            "temp_max": base_temp + 3,
            "apparent_temp_min": base_temp - 7,
            "apparent_temp_max": base_temp + 1,
            "wave_height": 0.5,
            "wind_speed": 3.0,
            "wind_direction": "북서",
            "tide_name": tide["type"],
            "tide_lunar_day": tide["lunar_day"],
            "tide_high": tide["high"],
            "tide_low": tide["low"],
            "tide_grade": tide["grade"],
            "suitability": _suitability(0.5, 3.0, tide["lunar_day"], "북서"),
        })
    return days


@router.get("/weather/forecast")
async def get_forecast(lat: float, lng: float):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"forecast_{lat:.4f}_{lng:.4f}.json"

    if cache_path.exists():
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        if age < CACHE_TTL:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    try:
        forecast = await _fetch_open_meteo(lat, lng)
        is_mock = False
    except Exception as exc:
        logger.warning("Open-Meteo forecast 실패 → 폴백: %s", exc)
        forecast = _fallback_days(lat, lng)
        is_mock = True

    result = {
        "location": {"lat": lat, "lng": lng},
        "forecast": forecast,
        "is_mock": is_mock,
        "fetched_at": datetime.now().isoformat(),
    }
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ── 시간대별 예보 ──────────────────────────────────────────────────────────────
@router.get("/weather/hourly")
async def get_hourly(lat: float, lng: float):
    key = f"{lat:.3f}_{lng:.3f}"
    now_ts = time.time()
    if key in _HOURLY_CACHE and now_ts - _HOURLY_CACHE[key]["ts"] < _HOURLY_TTL:
        return _HOURLY_CACHE[key]["data"]

    now = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            w_fut = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lng,
                    "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,weather_code",
                    "wind_speed_unit": "ms",
                    "timezone": "Asia/Seoul",
                    "forecast_days": 5,
                },
            )
            m_fut = client.get(
                "https://marine-api.open-meteo.com/v1/marine",
                params={
                    "latitude": lat, "longitude": lng,
                    "hourly": "wave_height,sea_surface_temperature",
                    "timezone": "Asia/Seoul",
                    "forecast_days": 5,
                },
            )
            w_resp, m_resp = await asyncio.gather(w_fut, m_fut, return_exceptions=True)

        w_resp.raise_for_status()
        wh = w_resp.json()["hourly"]

        waves: list | None = None
        sea_temps: list | None = None
        if not isinstance(m_resp, Exception):
            try:
                m_resp.raise_for_status()
                mh = m_resp.json()["hourly"]
                waves = mh.get("wave_height")
                sea_temps = mh.get("sea_surface_temperature")
            except Exception:
                pass

        times = wh["time"]
        now_str = now.strftime("%Y-%m-%dT%H:00")
        try:
            cur = times.index(now_str)
        except ValueError:
            cur = 0

        end = min(len(times), cur + 96)

        hours = []
        for i in range(cur, end):
            temp = round(float(wh["temperature_2m"][i] or 0), 1)
            wind = round(float(wh["wind_speed_10m"][i] or 0), 1)
            code = int(wh["weather_code"][i] or 0)
            wave = round(float(waves[i]) if waves and waves[i] is not None else 0.0, 2)
            water_temp = (
                round(float(sea_temps[i]), 1)
                if sea_temps and sea_temps[i] is not None
                else None
            )
            raw_wdir = wh.get("wind_direction_10m", [None] * (i + 1))[i]
            h_wind_dir = _wind_dir(float(raw_wdir) if raw_wdir is not None else None)
            h_str = times[i][11:16]  # "HH:MM"
            hours.append({
                "time": times[i],
                "hour": h_str,
                "icon": WEATHER_CODE_ICON.get(code, "🌤️"),
                "temp": temp,
                "wind": wind,
                "wind_dir": h_wind_dir,
                "wave": wave,
                "water_temp": water_temp,
                "is_now": (i == cur),
            })

        result = {"hours": hours, "is_mock": False}

    except Exception as exc:
        logger.warning("Hourly weather 실패 → 폴백: %s", exc)
        hours = []
        for i in range(96):
            dt = now + timedelta(hours=i)
            hours.append({
                "time": dt.strftime("%Y-%m-%dT%H:00"),
                "hour": dt.strftime("%H:00"),
                "icon": "🌤️",
                "temp": round(19.0 + i * 0.05, 1),
                "wind": 3.5,
                "wind_dir": "북서",
                "wave": 0.5,
                "water_temp": 18.5,
                "is_now": (i == 0),
            })
        result = {"hours": hours, "is_mock": True}

    _HOURLY_CACHE[key] = {"ts": now_ts, "data": result}
    return result
