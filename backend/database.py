import logging
import os
import re
import ssl
import uuid
from datetime import datetime
from urllib.parse import quote, urlparse
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

_SQLITE_FALLBACK = "sqlite+aiosqlite:///./fishing.db"


_PG_PREFIXES = ("postgres://", "postgresql://", "postgresql+asyncpg://")


def _build_database_url(raw: str) -> tuple[str, bool]:
    """
    Supabase/Railway DATABASE_URL → SQLAlchemy asyncpg 형식으로 안전하게 변환.

    처리 순서:
      1) 빈 값·SQLite → 그대로 반환
      2) 앞뒤 공백 / 따옴표 제거 (Railway 대시보드 복붙 오류 방어)
      3) postgres:// / postgresql:// → postgresql+asyncpg:// prefix 교체
      4) 비밀번호 특수문자 URL 인코딩 (! @ # $ % 등)
      5) 예외·비URL 값 → SQLite 폴백 + 명확한 경고 로그

    Returns:
        (database_url, is_postgres)
    """
    if not raw or raw.startswith("sqlite"):
        return raw or _SQLITE_FALLBACK, False

    # ── Step 1: 공백 / 따옴표 제거 ─────────────────────────────────────
    cleaned = raw.strip().strip("'\"")

    # ── Step 2: URL 형식 사전 검사 ──────────────────────────────────────
    if not any(cleaned.startswith(p) for p in _PG_PREFIXES):
        logger.error(
            "DATABASE_URL이 올바른 PostgreSQL URL 형식이 아닙니다.\n"
            "  받은 값 앞부분: %r\n"
            "  Railway Variables에 실제 Supabase 연결 문자열을 붙여넣었는지 확인하세요.\n"
            "  예시 형식: postgresql://user:password@host:6543/postgres\n"
            "  → SQLite 폴백으로 계속 실행합니다.",
            cleaned[:60],
        )
        return _SQLITE_FALLBACK, False

    try:
        # ── Step 3: prefix → postgresql+asyncpg:// ────────────────────
        if cleaned.startswith("postgres://"):
            url = "postgresql+asyncpg://" + cleaned[len("postgres://"):]
        elif cleaned.startswith("postgresql://") and "+asyncpg" not in cleaned:
            url = "postgresql+asyncpg://" + cleaned[len("postgresql://"):]
        else:
            url = cleaned  # 이미 postgresql+asyncpg://

        # ── Step 4: 비밀번호 URL 인코딩 ────────────────────────────────
        # postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB
        # 비밀번호의 ! @ # $ % 등 특수문자를 %XX 형태로 인코딩
        m = re.match(
            r"(postgresql\+asyncpg://)([^:@]+):([^@]+)@(.+)",
            url,
        )
        if m:
            scheme, user, password, rest = m.groups()
            safe_pw = quote(password, safe="")
            url = f"{scheme}{user}:{safe_pw}@{rest}"

        logger.info("DATABASE_URL 변환 완료 → host: %s", url.split("@")[-1].split("/")[0])
        return url, True

    except Exception as exc:
        logger.error("DATABASE_URL 변환 중 예외 → SQLite 폴백 (원인: %s)", exc)
        return _SQLITE_FALLBACK, False


# ── Database URL 확정 ────────────────────────────────────────────────────────
_raw_db_url = os.getenv("DATABASE_URL", _SQLITE_FALLBACK)
DATABASE_URL, _is_postgres = _build_database_url(_raw_db_url)

# ── 엔진 옵션 ────────────────────────────────────────────────────────────────
if _is_postgres:
    # Supabase/Railway PostgreSQL: SSL 필수
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE   # Supabase Pooler 인증서 체인 우회

    _engine_kwargs: dict = {
        "echo":         False,
        "pool_size":    5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "connect_args": {"ssl": _ssl_ctx, "timeout": 10},
    }
else:
    # SQLite (로컬 개발 또는 폴백)
    _engine_kwargs = {
        "echo":         False,
        "connect_args": {"check_same_thread": False},
    }

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    social_provider = Column(String)       # 'kakao' | 'naver'
    social_id = Column(String)
    nickname = Column(String)
    level = Column(String, default="beginner")  # 'beginner' | 'intermediate' | 'advanced'
    plan = Column(String, default="free")       # 'free' | 'premium'
    plan_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    email = Column(String, unique=True, index=True)
    profile_img = Column(String)
    is_admin = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Boat(Base):
    __tablename__ = "boats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    region = Column(String)
    departure = Column(String)
    price_per_person = Column(Integer)
    contact = Column(String)
    booking_url = Column(String)
    is_premium = Column(Boolean, default=False)
    premium_expires_at = Column(DateTime)
    source = Column(String)            # 크롤링 출처
    last_crawled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Gear(Base):
    __tablename__ = "gear"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    species_tags = Column(Text)        # JSON 배열: ["참돔","볼락"]
    level_tags = Column(Text)          # JSON 배열: ["beginner","intermediate"]
    guide = Column(Text)               # LLM 생성 가이드
    affiliate_url = Column(String)     # 쿠팡 파트너스 링크
    affiliate_source = Column(String)  # 'coupang' | 'naver'
    last_link_checked = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feed(Base):
    __tablename__ = "feed"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String)
    photo_url = Column(String)
    species = Column(String)
    weight_kg = Column(Float)
    region = Column(String)
    caught_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClickLog(Base):
    __tablename__ = "click_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String)
    item_type = Column(String)   # 'gear' | 'boat'
    user_id = Column(String)
    source_page = Column(String)
    clicked_at = Column(DateTime, default=datetime.utcnow)


class FishingSpot(Base):
    __tablename__ = "fishing_spots"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    lat = Column(Float)
    lng = Column(Float)
    description = Column(Text)
    species_tags = Column(Text)   # JSON ["감성돔","볼락"]
    features = Column(Text)       # JSON ["방파제","갯바위"]
    water_depth_m = Column(Float)
    bottom_type = Column(String)
    is_verified = Column(Boolean, default=False)
    avg_rating = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AffiliateProduct(Base):
    __tablename__ = "affiliate_products"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    url = Column(String)
    platform = Column(String)     # 'naver' | 'coupang'
    tags = Column(Text)           # JSON
    category = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PushNotification(Base):
    __tablename__ = "push_notifications"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    body = Column(Text)
    target = Column(String, default="all")  # 'all' | user_id
    sent_at = Column(DateTime)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id = Column(String)
    target_type = Column(String)  # 'post' | 'comment'
    target_id = Column(String)
    reason = Column(String)
    status = Column(String, default="pending")  # 'pending'|'resolved'|'dismissed'
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    """DB 초기화 — 실패해도 앱 시작은 계속 (Railway 배포 안전)"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB 초기화 완료: %s", DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "sqlite")
    except Exception as e:
        logger.error("DB 초기화 실패 (앱은 계속 실행): %s", e)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
