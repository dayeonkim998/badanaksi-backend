# 해역별 조석 보정값(분) 및 코드
SEA_AREA_META: dict[str, dict] = {
    "서해북부": {"tide_offset": -30, "code": "201"},
    "서해중부": {"tide_offset":   0, "code": "202"},
    "서해남부": {"tide_offset":  30, "code": "203"},
    "남해서부": {"tide_offset":  60, "code": "221"},
    "남해동부": {"tide_offset":  90, "code": "222"},
    "동해북부": {"tide_offset": 120, "code": "241"},
    "동해중부": {"tide_offset": 150, "code": "242"},
    "동해남부": {"tide_offset": 180, "code": "243"},
}


def get_sea_area(lat: float, lng: float) -> str:
    """위경도 → 해역명"""
    if lng < 126.0:
        if lat > 37.0:
            return "서해북부"
        return "서해중부" if lat > 35.0 else "서해남부"
    if lng > 128.5 or (lat < 34.5 and lng > 127.5):
        if lat > 37.5:
            return "동해북부"
        return "동해중부" if lat > 35.5 else "동해남부"
    return "남해서부" if lng < 127.5 else "남해동부"
