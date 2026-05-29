"""쿠팡 파트너스 링크 생성.

COUPANG_ACCESS_KEY + COUPANG_SECRET_KEY 모두 설정 시 실제 API 호출.
하나라도 미설정 시 쿠팡 검색 mock URL 반환.
"""
import hashlib
import hmac
import os
import urllib.parse
from datetime import datetime, timezone

import httpx

_ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY", "")
_SECRET_KEY = os.getenv("COUPANG_SECRET_KEY", "")
_PARTNERS_ID = os.getenv("COUPANG_PARTNERS_ID", "")

_API_BASE = "https://api-gateway.coupang.com"
_SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"


def _mock_product(keyword: str) -> dict:
    q = urllib.parse.quote(keyword)
    return {
        "keyword": keyword,
        "product_name": f"{keyword} 추천 상품",
        "affiliate_url": f"https://www.coupang.com/np/search?q={q}&channel=user",
        "price": None,
        "thumbnail": None,
        "is_mock": True,
    }


def _auth_header(method: str, path: str, query: str) -> dict:
    dt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    message = f"{dt}\n{method}\n{path}\n{query}"
    sig = hmac.new(
        _SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Authorization": (
            f"CEA algorithm=HmacSHA256, access-key={_ACCESS_KEY},"
            f" signed-date={dt}, signature={sig}"
        ),
        "Content-Type": "application/json",
    }


async def _real_products(keyword: str) -> list[dict]:
    raw_params: dict = {"keyword": keyword, "limit": "5"}
    if _PARTNERS_ID:
        raw_params["subId"] = _PARTNERS_ID
    query = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in sorted(raw_params.items())
    )
    headers = _auth_header("GET", _SEARCH_PATH, query)

    async with httpx.AsyncClient(timeout=8.0) as cli:
        r = await cli.get(f"{_API_BASE}{_SEARCH_PATH}?{query}", headers=headers)
        r.raise_for_status()
        items = r.json().get("data", {}).get("productData") or []

    return [
        {
            "keyword": keyword,
            "product_name": p.get("productName", keyword),
            "affiliate_url": p.get("productUrl", ""),
            "price": p.get("salePriceWithTax"),
            "thumbnail": p.get("productImage"),
            "is_mock": False,
        }
        for p in items[:3]
    ]


async def generate_affiliate_links(keywords: list[str]) -> list[dict]:
    if not keywords:
        return []

    use_real = bool(_ACCESS_KEY and _SECRET_KEY)
    results: list[dict] = []

    for kw in keywords[:3]:
        if use_real:
            try:
                results.extend(await _real_products(kw))
                continue
            except Exception:
                pass  # 실패 시 mock으로 폴백
        results.append(_mock_product(kw))

    return results
