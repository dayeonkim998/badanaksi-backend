"""
비주얼 서치 라우터 — POST /api/vision/search

Claude Vision으로 어종·용품 인식 후:
  1. 쿠팡 파트너스 상품 (keyword 기반 실시간 검색)
  2. 네이버 브랜드커넥트 상품 (태그 기반 즉시 매칭)
를 함께 반환한다.
"""
import base64

from fastapi import APIRouter, File, HTTPException, UploadFile

from data.affiliate_products import match_products as naver_match
from skills.vision_analyzer.analyze import analyze_image
from skills.vision_analyzer.coupang_links import generate_affiliate_links

router = APIRouter()

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/vision/search")
async def vision_search(image: UploadFile = File(...)):
    content_type = (image.content_type or "image/jpeg").split(";")[0].strip()
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(400, "지원하지 않는 이미지 형식입니다 (JPEG·PNG·WebP·GIF)")

    data = await image.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, "이미지 크기는 5MB 이하여야 합니다")

    b64 = base64.b64encode(data).decode()
    analysis = await analyze_image(b64, content_type)

    # 1. 쿠팡 파트너스 — keyword 기반 검색
    coupang_products = await generate_affiliate_links(analysis.get("keywords", []))

    # 2. 네이버 브랜드커넥트 — 어종명 + 관련용품 태그 기반 즉시 매칭
    naver_tags: list[str] = []
    if analysis.get("name"):
        naver_tags.append(analysis["name"])
    naver_tags.extend(analysis.get("related_gear", []))
    naver_tags.extend(analysis.get("keywords", []))
    naver_products = naver_match(naver_tags, limit=5)

    return {
        "analysis":       analysis,
        "products":       coupang_products,     # 쿠팡 파트너스 (기존 호환)
        "naver_products": naver_products,       # 네이버 브랜드커넥트 (신규)
    }
