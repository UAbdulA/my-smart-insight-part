from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

from app.core.database import AsyncSessionLocal
from app.models.insight import Insight, InsightStatus
from app.models.feedback_models import AuditLog, Feedback

router = APIRouter(prefix="/insights", tags=["status & analytics"])

# Схема для обновления статуса (определим здесь, чтобы не зависеть от чужих файлов)
class StatusUpdate(BaseModel):
    new_status: InsightStatus
    changed_by: str = "system"
    comment: Optional[str] = None

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

@router.patch("/{id}/status")
async def update_status(id: uuid.UUID, update: StatusUpdate, session: AsyncSession = Depends(get_session)):
    # Найти инсайт по ID
    result = await session.execute(select(Insight).where(Insight.id == id))
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    old_status = insight.status
    new_status = update.new_status

    # Проверка допустимости перехода (простая логика: Draft -> Pending -> Posted, без отката)
    if new_status == old_status:
        raise HTTPException(status_code=400, detail="Already in this status")
    if old_status == InsightStatus.POSTED and new_status != InsightStatus.POSTED:
        raise HTTPException(status_code=400, detail="Cannot revert from Posted")

    # Обновляем статус
    insight.status = new_status
    insight.updated_at = datetime.utcnow()

    # Пишем аудит
    audit_record = AuditLog(
        insight_id=id,
        changed_by=update.changed_by,
        old_status=old_status,
        new_status=new_status
    )
    session.add(audit_record)

    # Если есть комментарий — сохраняем как Feedback
    if update.comment:
        feedback_record = Feedback(
            insight_id=id,
            comment=update.comment,
            author=update.changed_by,
            feedback_type="manual"
        )
        session.add(feedback_record)

    await session.commit()
    return {"status": "ok", "old_status": old_status, "new_status": new_status}

@router.get("/analytics/summary")
async def get_analytics(session: AsyncSession = Depends(get_session)):
    # Подсчёт количества инсайтов по статусам
    stmt = select(Insight.status, func.count()).group_by(Insight.status)
    result = await session.execute(stmt)
    stats = {row[0]: row[1] for row in result}
    total = sum(stats.values())
    return {"total": total, "by_status": stats}