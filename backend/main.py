from dotenv import load_dotenv
load_dotenv()  # .env를 임포트보다 먼저 로드

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from api.weather import router as weather_router
from api.forecast import router as forecast_router
from api.vision import router as vision_router
from api.ocean import router as ocean_router
from api.gear import router as gear_router
from api.recommend import router as recommend_router
from api.spots import router as spots_router
from api.tide import router as tide_router
from api.search import router as search_router
from api.affiliate import router as affiliate_router
from api.admin.auth import router as admin_auth_router
from api.admin.users import router as admin_users_router
from api.admin.products import router as admin_products_router
from api.admin.spots import router as admin_spots_router
from api.admin.boats import router as admin_boats_router
from api.admin.community import router as admin_community_router
from api.admin.notifications import router as admin_notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="바다낚시 플랫폼 API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # 개발 환경: React Native / Expo Go / 브라우저 전체 허용
    # 프로덕션에서는 실제 도메인으로 제한 필요
    allow_origins=["*"],
    allow_credentials=False,   # allow_origins=["*"] 와 함께 True 불가
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/weather → 실제 기상청 API 연동
app.include_router(weather_router, prefix="/api")
app.include_router(forecast_router, prefix="/api")
# /api/vision/search → Claude Vision + 쿠팡 파트너스
app.include_router(vision_router, prefix="/api")
# /api/ocean → 국립수산과학원 실시간어장정보 + 연안정지관측
app.include_router(ocean_router, prefix="/api")
# /api/gear → DB 조회 + 어종 필터
app.include_router(gear_router, prefix="/api")
# /api/recommend → 계절·해역·수온 기반 어종 확률 추천
app.include_router(recommend_router, prefix="/api")
app.include_router(spots_router, prefix="/api")
# /api/tide → 조석예보 API (국립해양조사원)
app.include_router(tide_router, prefix="/api")
# /api/search/location → Nominatim 지역 검색 프록시 (CORS 우회)
app.include_router(search_router, prefix="/api")
# /api/affiliate/naver → 네이버 브랜드커넥트 태그 기반 상품 조회
app.include_router(affiliate_router, prefix="/api")

# 관리자 API (is_admin 검증)
app.include_router(admin_auth_router,          prefix="/api")
app.include_router(admin_users_router,         prefix="/api")
app.include_router(admin_products_router,      prefix="/api")
app.include_router(admin_spots_router,         prefix="/api")
app.include_router(admin_boats_router,         prefix="/api")
app.include_router(admin_community_router,     prefix="/api")
app.include_router(admin_notifications_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Railway 헬스체크 엔드포인트"""
    return {"status": "ok", "service": "badanaksi-api"}


@app.get("/api/boats")
async def get_boats(lat: float, lng: float):
    # TODO: DB 조회
    return {
        "location": {"lat": lat, "lng": lng},
        "boats": [
            {
                "id": "boat-001",
                "name": "예시 낚시배",
                "region": "부산",
                "departure": "부산 기장",
                "price_per_person": 70000,
                "contact": "010-0000-0000",
                "booking_url": "https://example.com",
            }
        ],
    }


@app.post("/api/feed")
async def create_feed(data: dict):
    # Phase 2 구현 예정
    return {"message": "Phase 2에서 오픈됩니다.", "status": "not_implemented"}
