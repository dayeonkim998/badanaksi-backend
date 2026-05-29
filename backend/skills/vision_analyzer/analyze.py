"""Claude Vision API로 낚시 관련 이미지를 분석한다."""
import json

from anthropic import AsyncAnthropic

_client = AsyncAnthropic()

_PROMPT = """이 사진을 낚시 관점에서 분석해주세요. 아래 JSON 형식으로만 응답해주세요.

{
  "category": "fish" | "gear" | "unknown",
  "name": "아이템 한국어 이름",
  "name_en": "아이템 영어 이름",
  "keywords": ["쿠팡검색키워드1", "쿠팡검색키워드2", "쿠팡검색키워드3"],
  "confidence": 0.0~1.0,
  "description": "간단한 설명 50자 이내",
  "related_gear": ["관련용품1", "관련용품2", "관련용품3"]
}

분류 기준:
- fish: 어종 (참돔, 볼락, 방어, 농어, 갈치 등)
- gear: 낚시 용품 (낚싯대, 릴, 루어, 채비, 낚시가방 등)
- unknown: 낚시와 무관한 사진

keywords: 쿠팡에서 검색할 구체적인 키워드 (예: "참돔 전용 로드", "참돔 채비 세트")
related_gear: 이 어종·용품에 어울리는 낚시 용품 이름

JSON만 반환하세요. 다른 텍스트 없이."""

_FALLBACK = {
    "category": "unknown",
    "name": "인식 실패",
    "name_en": "Unknown",
    "keywords": [],
    "confidence": 0.0,
    "description": "사진을 다시 찍어주세요",
    "related_gear": [],
}


async def analyze_image(b64_image: str, media_type: str) -> dict:
    try:
        msg = await _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception:
        return dict(_FALLBACK)
