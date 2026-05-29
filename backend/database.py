import os
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Railway/Supabase는 DATABASE_URL 환경변수로 PostgreSQL URL을 주입
# 로컬 개발: SQLite 사용
_raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./fishing.db")

if _raw_db_url.startswith("postgres://"):
    # Railway는 postgres:// 접두사를 사용 → asyncpg 드라이버로 변환
    DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_db_url.startswith("postgresql://") and "+asyncpg" not in _raw_db_url:
    DATABASE_URL = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _raw_db_url

# PostgreSQL: connect_args 불필요 / SQLite: check_same_thread=False 필요
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=_connect_args)
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
