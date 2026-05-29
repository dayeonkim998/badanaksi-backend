"""관리자 인증 미들웨어"""
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

_security = HTTPBearer()
ADMIN_SECRET = os.getenv("JWT_SECRET", "dev-secret")


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """
    Authorization: Bearer <token> 헤더 검증.
    토큰 payload에 is_admin=True 가 있어야 통과.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, ADMIN_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 만료되었습니다")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다")

    if not payload.get("is_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자 권한이 필요합니다")

    return payload


def create_admin_token(email: str, user_id: str) -> str:
    """관리자 JWT 토큰 생성"""
    import time
    payload = {
        "sub":      user_id,
        "email":    email,
        "is_admin": True,
        "iat":      int(time.time()),
        "exp":      int(time.time()) + 86400 * 7,  # 7일
    }
    return jwt.encode(payload, ADMIN_SECRET, algorithm="HS256")
