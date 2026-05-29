"""
네이버 브랜드커넥트 제휴 상품 라우터

GET /api/affiliate/naver?tags=tag1,tag2&category=낚싯대&limit=5
GET /api/affiliate/naver/all?category=채비
GET /api/affiliate/naver/{product_id}

N 네이버쇼핑 출처 배지 + AD 표시는 응답 내 모든 항목에 포함됨.
"""
from fastapi import APIRouter, HTTPException

from data.affiliate_products import get_all, get_by_id, match_products

router = APIRouter()


@router.get("/affiliate/naver")
def get_naver_by_tags(
    tags: str = "",
    category: str | None = None,
    limit: int = 5,
):
    """태그 기반 네이버 제휴 상품 검색.

    - tags: 쉼표 구분 태그 (예: 볼락,루어낚시)
    - category: 상품 카테고리 필터 (낚싯대·채비·보조용품 등)
    - limit: 최대 반환 개수 (1~10)
    """
    limit = max(1, min(10, limit))
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    products = match_products(tag_list, limit=limit, category=category)
    return {"tags": tag_list, "category": category, "products": products}


@router.get("/affiliate/naver/all")
def get_all_naver(category: str | None = None):
    """전체 네이버 제휴 상품 목록."""
    return {"category": category, "products": get_all(category)}


@router.get("/affiliate/naver/{product_id}")
def get_naver_product(product_id: str):
    """ID로 단일 상품 조회."""
    product = get_by_id(product_id)
    if not product:
        raise HTTPException(404, f"상품을 찾을 수 없습니다: {product_id}")
    return product
