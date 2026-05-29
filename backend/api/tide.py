"""조석예보 API 라우터"""
from datetime import datetime
from fastapi import APIRouter
from skills.weather_fetcher.fetch_tide import fetch_tide

router = APIRouter()


@router.get("/tide")
async def get_tide(lat: float, lng: float):
    """
    가장 가까운 관측소의 오늘·내일 고조/저조 시간·높이 + 물때 이름 반환.
    실 API 실패 시 달 계산식으로 자동 fallback.
    """
    return await fetch_tide(lat, lng, datetime.now())
