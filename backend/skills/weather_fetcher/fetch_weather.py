"""
날씨 데이터 조회
우선순위: 기상청 fct_afs_do.php (KMA) → Open-Meteo (무료 폴백) → 계절 기본값
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from .regions import get_sea_area

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent.parent / "output" / "weather_cache"
CACHE_TTL = 3600  # seconds


def _forecast_tm() -> str:
    """가장 최근 기상청 발표 시각 (YYYYMMDDHHMI)"""
    now = datetime.now()
    base_hours = [0, 6, 12, 18]
    adjusted = now - timedelta(minutes=30)
    h = adjusted.hour
    valid = [bh for bh in base_hours if bh <= h]
    base_h = valid[-1] if valid else 18
    if not valid:
        adjusted -= timedelta(days=1)
        base_h = 18
    return adjusted.strftime(f"%Y%m%d{base_h:02d}00")


def _parse_kma(text: str, area: str) -> dict | None:
    """기상청 해상예보 텍스트 파싱. 해당 해역 미발견 시 None 반환."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or area not in line:
            continue

        wind_speed = 4.0
        wave_height = 0.5
        condition = "맑음"

        wave_m = re.search(r'(\d+\.\d+)\s*[~\-]\s*(\d+\.\d+)', line)
        if wave_m:
            try:
                wave_height = round((float(wave_m.group(1)) + float(wave_m.group(2))) / 2, 1)
            except ValueError:
                pass

        for wmin_s, wmax_s in re.findall(r'(\d+)\s*[~\-]\s*(\d+)', line):
            try:
                avg_kt = (int(wmin_s) + int(wmax_s)) / 2
                if 1 < avg_kt < 80:
                    wind_speed = round(avg_kt * 0.5144, 1)
                    break
            except ValueError:
                pass

        for cond in ("맑음", "구름많음", "흐림", "비", "눈"):
            if cond in line:
                condition = cond
                break

        return {"wind_speed": wind_speed, "wave_height": wave_height, "condition": condition}

    return None


def _wmo_desc(code: int) -> str:
    if code == 0: return "맑음"
    if code <= 3: return ["", "맑음", "구름많음", "흐림"][code]
    if code in (45, 48): return "안개"
    if code in (51, 53, 55): return "이슬비"
    if code in (61, 63, 65): return "비"
    if code in (71, 73, 75): return "눈"
    if code in (80, 81, 82): return "소나기"
    if code == 95: return "뇌우"
    return "흐림"


def _deg_dir(deg: float) -> str:
    dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return dirs[round(float(deg) / 45) % 8]


async def _fetch_open_meteo(lat: float, lng: float, client: httpx.AsyncClient) -> dict:
    """Open-Meteo 현재·시간별·일별 데이터 조회"""
    today = datetime.now().strftime("%Y-%m-%d")

    # ① 기상 예보 (현재 + 시간별 + 일별)
    wr = await client.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lng,
            "current": (
                "temperature_2m,wind_speed_10m,wind_direction_10m,"
                "weather_code,apparent_temperature,precipitation_probability"
            ),
            "hourly": (
                "temperature_2m,wind_speed_10m,wind_direction_10m,"
                "weather_code,precipitation_probability"
            ),
            "daily": "sunrise,sunset,uv_index_max",
            "wind_speed_unit": "ms",
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        },
    )
    wr.raise_for_status()
    wj = wr.json()
    curr = wj.get("current", {})

    # ② 해양 (현재 + 시간별 파고) — 실패해도 계속
    wave_cur = 0.5
    hourly_wave: dict[str, float] = {}
    try:
        mr = await client.get(
            "https://marine-api.open-meteo.com/v1/marine",
            params={
                "latitude": lat, "longitude": lng,
                "current": "wave_height",
                "hourly": "wave_height",
                "timezone": "Asia/Seoul",
                "forecast_days": 1,
            },
        )
        mr.raise_for_status()
        mj = mr.json()
        wave_cur = float(mj.get("current", {}).get("wave_height") or 0.5)
        mh = mj.get("hourly", {})
        for t, wh in zip(mh.get("time", []), mh.get("wave_height", [])):
            if t and t.startswith(today):
                hourly_wave[t[-5:]] = round(float(wh or wave_cur), 2)
    except Exception as exc:
        logger.debug("Marine API 실패: %s", exc)

    code = int(curr.get("weather_code", 0) or 0)

    # 시간별 데이터 (오늘 24개)
    wh = wj.get("hourly", {})
    times = wh.get("time", [])
    hourly: list[dict] = []
    for i, t in enumerate(times):
        if not (t and t.startswith(today)):
            continue
        ts = t[-5:]
        wc = int((wh.get("weather_code") or [0])[i] or 0)
        hourly.append({
            "time": ts,
            "temp":       round(float((wh.get("temperature_2m") or [18])[i] or 18), 1),
            "wind_speed": round(float((wh.get("wind_speed_10m") or [3])[i] or 3), 1),
            "wind_dir_deg": round(float((wh.get("wind_direction_10m") or [180])[i] or 180)),
            "weather_code": wc,
            "weather_desc": _wmo_desc(wc),
            "precip_prob": int((wh.get("precipitation_probability") or [0])[i] or 0),
            "wave_height":  hourly_wave.get(ts, wave_cur),
        })

    # 일별 (일출/일몰/UV)
    daily = wj.get("daily", {})
    def _daily_val(key: str, default):
        arr = daily.get(key, [])
        idx = next((i for i, d in enumerate(daily.get("time", [])) if d == today), 0)
        return arr[idx] if arr and idx < len(arr) else default

    sunrise_raw = _daily_val("sunrise", f"{today}T05:30")
    sunset_raw  = _daily_val("sunset",  f"{today}T19:40")
    uv_index    = float(_daily_val("uv_index_max", 3.0) or 3.0)

    return {
        "wind_speed":         round(float(curr.get("wind_speed_10m", 3.0) or 3.0), 1),
        "wind_direction_deg": float(curr.get("wind_direction_10m", 180) or 180),
        "wave_height":        round(wave_cur, 2),
        "temp":               round(float(curr.get("temperature_2m", 18.0) or 18.0), 1),
        "feels_like":         round(float(curr.get("apparent_temperature", 16.0) or 16.0), 1),
        "condition":          _wmo_desc(code),
        "weather_code":       code,
        "precipitation_prob": int(curr.get("precipitation_probability", 0) or 0),
        "uv_index":           round(uv_index, 1),
        "hourly":             hourly,
        "sunrise":            str(sunrise_raw)[-5:],
        "sunset":             str(sunset_raw)[-5:],
    }


async def fetch_weather(lat: float, lng: float, date: str | None = None) -> dict:
    today = date or datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{lat:.4f}_{lng:.4f}_{today}"
    cache_path = CACHE_DIR / f"{cache_key}.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 유효 캐시 반환
    if cache_path.exists():
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        if age < CACHE_TTL:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    area = get_sea_area(lat, lng)
    weather_fields: dict | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1순위: Open-Meteo (hourly/daily 포함) — 항상 시도
        om_data: dict | None = None
        try:
            om_data = await _fetch_open_meteo(lat, lng, client)
            weather_fields = om_data
        except Exception as exc:
            logger.warning("Open-Meteo 실패: %s", exc)

        # 2순위: 기상청 KMA 해상예보로 파고·풍속 덮어쓰기 (키 있고 성공할 때)
        api_key = os.getenv("WEATHER_API_KEY", "")
        if api_key and weather_fields is not None:
            try:
                resp = await client.get(
                    "https://apihub.kma.go.kr/api/typ01/url/fct_afs_do.php",
                    params={"authKey": api_key, "tm": _forecast_tm(), "stn": 0, "help": 0},
                )
                resp.raise_for_status()
                parsed = _parse_kma(resp.text, area)
                if parsed:
                    weather_fields["wind_speed"]  = parsed["wind_speed"]
                    weather_fields["wave_height"]  = parsed["wave_height"]
                    weather_fields["condition"]    = parsed["condition"]
            except Exception as exc:
                logger.debug("KMA 덮어쓰기 실패 (무시): %s", exc)

    # 3순위: 정적 계절 기본값 (네트워크 불가)
    if weather_fields is None:
        season_temp = {1:5,2:7,3:12,4:17,5:21,6:24,7:27,8:28,9:23,10:18,11:12,12:7}
        weather_fields = {
            "wind_speed": 4.0, "wave_height": 0.5,
            "temp": season_temp.get(datetime.now().month, 18),
            "condition": "맑음", "hourly": [], "sunrise": "05:30", "sunset": "19:40",
        }

    # hourly·sunrise·sunset 을 최상위로 승격 (api/weather.py 에서 직접 접근)
    result = {
        "location":  {"lat": lat, "lng": lng},
        "area":      area,
        "weather":   weather_fields,
        "hourly":    weather_fields.get("hourly", []),
        "sunrise":   weather_fields.get("sunrise", "05:30"),
        "sunset":    weather_fields.get("sunset", "19:40"),
        "fetched_at": datetime.now().isoformat(),
    }
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
