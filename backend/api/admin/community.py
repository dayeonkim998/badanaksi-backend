"""관리자 - 커뮤니티 신고 처리 API"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Feed, Report, get_session
from api.admin.middleware import require_admin

router = APIRouter(prefix="/admin/community", tags=["admin-community"])


@router.get("/reports")
async def list_reports(
    status: str = "pending",
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Report).where(Report.status == status).order_by(Report.created_at.desc())
    )
    reports = result.scalars().all()
    return {"items": [
        {
            "id": r.id, "reporter_id": r.reporter_id,
            "target_type": r.target_type, "target_id": r.target_id,
            "reason": r.reason, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in reports
    ]}


class ReportAction(BaseModel):
    action: str   # 'resolve' | 'dismiss' | 'delete_content'


@router.post("/reports/{report_id}/action")
async def handle_report(
    report_id: str,
    body: ReportAction,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        from fastapi import HTTPException; raise HTTPException(404, "신고 없음")
    if body.action == "resolve":
        report.status = "resolved"
    elif body.action == "dismiss":
        report.status = "dismissed"
    elif body.action == "delete_content" and report.target_type == "post":
        feed_result = await session.execute(select(Feed).where(Feed.id == report.target_id))
        feed = feed_result.scalar_one_or_none()
        if feed:
            await session.delete(feed)
        report.status = "resolved"
    await session.commit()
    return {"ok": True, "status": report.status}
