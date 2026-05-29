"""
낚시 앱 제휴 상품 카탈로그
────────────────────────────────────────────────────────────
[지원 플랫폼]
  naver   → N 네이버쇼핑  (네이버 브랜드커넥트)
  coupang → 쿠팡파트너스

[법적 의무]
  - AD 배지 필수 (양쪽 약관)
  - 가격 표시 금지 (쿠팡 파트너스 약관)
  - 플랫폼 출처 표시 의무 (네이버 커머스 약관)

────────────────────────────────────────────────────────────
★ 상품 추가·수정 가이드 ★

공통 필드 (플랫폼 무관):
  "id"          : 고유 식별자  (nv_NNN = 네이버 / cp_NNN = 쿠팡)
  "name"        : 상품명      ← 여기만 바꾸면 화면에 바로 반영
  "description" : 설명 50자 이내
  "url"         : 쿠팡/네이버 제휴 단축 URL
  "tags"        : 태그 리스트 — 아래 예시 참고
                  어종명: "볼락", "광어", "감성돔", "방어"
                  용도:   "루어낚시", "찌낚시", "에깅"
                  카테고리: "낚싯대", "릴", "채비", "미끼"
  "category"    : 탭 필터용 — 낚싯대 | 릴 | 채비 | 미끼 | 보조용품

platform·is_ad·ad_label·source_label 은 platform 값에서 자동 주입됨.
  → "platform": "naver"   or   "platform": "coupang"

════ 예시 ═══════════════════════════════════════════════════
  {
      "id":          "cp_006",           # 다음 순번으로 채번
      "name":        "상품명 직접 입력",  # ← 쿠팡 상품페이지에서 복사
      "description": "간단 설명",
      "url":         "https://link.coupang.com/a/XXXXXXXX",
      "tags":        ["태그1", "태그2"],
      "category":    "낚싯대",
      "platform":    "coupang",
  }
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

# ─── 네이버 브랜드커넥트 상품 ────────────────────────────────────────────────
NAVER_PRODUCTS: list[dict] = [
    {
        "id":          "nv_001",
        "name":        "낚시기포기",
        "description": "활어 보관·수조 산소 공급용 낚시 전용 기포기",
        "url":         "https://naver.me/xNpnk9Nv",
        "tags":        ["기포기", "보조용품", "활어", "수조", "산소"],
        "category":    "보조용품",
        "platform":    "naver",
    },
    {
        "id":          "nv_002",
        "name":        "봉돌 고리추",
        "description": "갑오징어·한치·문어·우럭·광어 채비용 고리봉돌",
        "url":         "https://naver.me/5qLc6tOK",
        "tags":        [
            "봉돌", "고리추", "채비",
            "갑오징어", "한치", "문어", "낙지", "주꾸미",
            "우럭", "조피볼락", "광어", "넙치",
            "바닥낚시", "에깅", "외줄낚시",
        ],
        "category":    "채비",
        "platform":    "naver",
    },
    {
        "id":          "nv_003",
        "name":        "아부가르시아 새턴3 낚싯대",
        "description": "루어낚시 전용 스피닝 로드 — 볼락·광어·우럭에 적합",
        "url":         "https://naver.me/FgETetMe",
        "tags":        [
            "낚싯대", "로드", "스피닝로드", "루어낚시",
            "볼락", "조피볼락", "광어", "넙치", "우럭",
            "아부가르시아", "아징", "라이트게임",
        ],
        "category":    "낚싯대",
        "platform":    "naver",
    },
]

# ─── 쿠팡 파트너스 상품 ──────────────────────────────────────────────────────
# ★ name / description / tags / category 는 직접 수정하세요.
#   쿠팡 상품 페이지에서 상품명을 확인하여 name에 입력하면 됩니다.
COUPANG_PRODUCTS: list[dict] = [
    {
        "id":          "cp_001",
        # ↓ 쿠팡 상품페이지 확인 후 수정
        "name":        "낚시 루어 세트",
        "description": "다양한 어종을 공략하는 루어 모음 세트 (임시명 — 직접 수정)",
        "url":         "https://link.coupang.com/a/d7yytRQ4DA",
        "tags":        ["루어", "루어세트", "루어낚시", "볼락", "농어", "광어"],
        "category":    "채비",
        "platform":    "coupang",
    },
    {
        "id":          "cp_002",
        # ↓ 쿠팡 상품페이지 확인 후 수정
        "name":        "낚시 스피닝릴",
        "description": "루어·찌낚시 범용 스피닝릴 (임시명 — 직접 수정)",
        "url":         "https://link.coupang.com/a/d7yB0pQPNk",
        "tags":        ["릴", "스피닝릴", "루어낚시", "찌낚시", "볼락", "감성돔"],
        "category":    "릴",
        "platform":    "coupang",
    },
    {
        "id":          "cp_003",
        # ↓ 쿠팡 상품페이지 확인 후 수정
        "name":        "낚시 바늘 채비 세트",
        "description": "다양한 어종용 바늘·채비 모음 세트 (임시명 — 직접 수정)",
        "url":         "https://link.coupang.com/a/d7yDA9TXOK",
        "tags":        ["바늘", "채비", "낚시바늘", "갈치", "고등어", "전갱이", "찌낚시"],
        "category":    "채비",
        "platform":    "coupang",
    },
    {
        "id":          "cp_004",
        # ↓ 쿠팡 상품페이지 확인 후 수정
        "name":        "냉동 크릴새우 (낚시 미끼용)",
        "description": "감성돔·고등어·전어 찌낚시 밑밥·미끼용 크릴 (임시명 — 직접 수정)",
        "url":         "https://link.coupang.com/a/d7yFl752ui",
        "tags":        [
            "크릴", "미끼", "밑밥", "크릴새우",
            "감성돔", "고등어", "전어", "참조기", "찌낚시",
        ],
        "category":    "미끼",
        "platform":    "coupang",
    },
    {
        "id":          "cp_005",
        # ↓ 쿠팡 상품페이지 확인 후 수정
        "name":        "낚시 가방 (태클백)",
        "description": "채비·용품 수납용 낚시 전용 가방 (임시명 — 직접 수정)",
        "url":         "https://link.coupang.com/a/d7yGB18rN6",
        "tags":        ["낚시가방", "태클백", "보조용품", "수납", "채비정리"],
        "category":    "보조용품",
        "platform":    "coupang",
    },
]

# ─── 전체 카탈로그 (Naver + Coupang) ────────────────────────────────────────
ALL_PRODUCTS: list[dict] = NAVER_PRODUCTS + COUPANG_PRODUCTS

# ─── 플랫폼별 공통 필드 자동 주입 ────────────────────────────────────────────
_PLATFORM_COMMON: dict[str, dict] = {
    "naver": {
        "is_ad":        True,
        "ad_label":     "AD",
        "source_label": "N 네이버쇼핑",
    },
    "coupang": {
        "is_ad":        True,
        "ad_label":     "AD",
        "source_label": "쿠팡파트너스",
    },
}


def _inject(product: dict) -> dict:
    """platform 값으로 공통 필드를 주입해 완성된 상품 딕셔너리 반환."""
    common = _PLATFORM_COMMON.get(product.get("platform", "naver"), {})
    return {**product, **common}


# ─── 조회 함수 ────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.strip().lower()


def match_products(
    tags: list[str],
    *,
    limit: int = 5,
    category: str | None = None,
    platform: str | None = None,
) -> list[dict]:
    """태그 기반 상품 검색 (Naver + Coupang 통합).

    Args:
        tags:     어종명·카테고리·용도 등 태그 목록
        limit:    최대 반환 개수 (기본 5)
        category: 카테고리 필터 ('낚싯대'·'채비' 등)
        platform: 플랫폼 필터 ('naver' | 'coupang' | None=전체)
    """
    if not tags:
        return []

    query = {_normalize(t) for t in tags}
    scored: list[tuple[int, dict]] = []

    for product in ALL_PRODUCTS:
        if category and product.get("category") != category:
            continue
        if platform and product.get("platform") != platform:
            continue
        product_tags = {_normalize(t) for t in product["tags"]}
        overlap = len(query & product_tags)
        if overlap > 0:
            scored.append((overlap, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_inject(p) for _, p in scored[:limit]]


def get_all(
    category: str | None = None,
    platform: str | None = None,
) -> list[dict]:
    """전체 상품 반환 (카테고리·플랫폼 필터 선택)."""
    products = ALL_PRODUCTS
    if category:
        products = [p for p in products if p.get("category") == category]
    if platform:
        products = [p for p in products if p.get("platform") == platform]
    return [_inject(p) for p in products]


def get_by_id(product_id: str) -> dict | None:
    """ID로 단일 상품 조회."""
    for p in ALL_PRODUCTS:
        if p["id"] == product_id:
            return _inject(p)
    return None
