"""관리자 - 푸시 알림 발송 API"""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import PushNotification, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


class NotifBody(BaseModel):
    title: str
    body: str
    target: str = "all"   # 'all' | user_id


@router.post("/send")
async def send_notification(
    payload: NotifBody,
    admin: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    n = PushNotification(
        title=payload.title, body=payload.body,
        target=payload.target, sent_at=datetime.utcnow(),
        created_by=admin.get("sub", "admin"),
    )
    session.add(n)
    await session.commit()
    # TODO: 실제 FCM / Expo Push 연동
    return {"ok": True, "message": f"알림 발송 완료 (대상: {payload.target})", "id": n.id}


@router.get("/history")
async def notification_history(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PushNotification).order_by(PushNotification.created_at.desc()).limit(50)
    )
    items = result.scalars().all()
    return {"items": [
        {
            "id": n.id, "title": n.title, "body": n.body,
            "target": n.target, "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        } for n in items
    ]}
