import os
import html
import logging
import traceback
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator  
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# 1. Загрузка переменных окружения до импорта настроек БД
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Импорты из архитектуры вашего друга
from app.api.v1.telegram import router as telegram_router
from app.core.database import Base as AppBase, async_engine, get_async_session
from app.models import Insight, InsightSource, InsightStatus, StatusLog
from app.services.audit import log_status_change
from app.services.analyzer import analyze_raw_text
from app.services.responder import generate_smart_reply
from app.connectors.tg_bridge import send_approval_card
from app.schemas import InsightRead, StatusLogRead, WBWebhookRequest  

# Исправленная схема: автоматически переводит входящий текст в ВЕРХНИЙ регистр
class LocalStatusUpdate(BaseModel):
    new_status: str = Field(..., description="Новый статус: draft, pending или posted")
    changed_by: str = Field(default="mentor", description="Кто изменил статус")
    comment: str | None = Field(default=None, description="Комментарий/фидбек ментора")

    @field_validator("new_status")
    @classmethod
    def convert_status_to_uppercase(cls, value: str) -> str:
        # Переводим всё в верхний регистр (pending -> PENDING), чтобы Enum базы данных не ругался
        return value.strip().upper()

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

# Автоматически создаем таблицы в базе данных при старте сервера
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)
    yield

app = FastAPI(
    title="Smart Insight Desk MVP",
    description="Система сбора, нормализации, анализа и публикации инсайтов",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,  # Подключили автоматическое создание таблиц
)

app.include_router(telegram_router)

def _get_telegram_token() -> str | None:
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_TOKEN")
        or os.getenv("ORCHESTRATOR_BOT_TOKEN")
    )

def _get_telegram_chat_id() -> int | None:
    raw_value = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("ANALYTICS_CHAT_ID")
        or os.getenv("BOT_CHAT_ID")
    )
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None

@app.get("/")
async def root():
    return {
        "status": "Работает!",
        "message": "Smart Insight Desk MVP запущен. Откройте /docs для Swagger UI."
    }

# БЛОК Б1: Обработка вебхуков WB
@app.post(
    "/api/v1/webhook/wb",
    response_model=InsightRead,
    tags=["Webhooks"],
    summary="Receive new Wildberries review",
)
async def webhook_wb(
    payload: WBWebhookRequest,  
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Входной текст не может быть пустым.")

    try:
        analysis = await analyze_raw_text(payload.text)
        
        insight = Insight(
            source=InsightSource.WB,
            raw_text=payload.text,
            normalized_text=analysis["normalized_text"],
            sentiment_score=analysis["sentiment_score"],
            pain_category=analysis["pain_category"],
            status=InsightStatus.DRAFT,
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)

        ai_reply = await generate_smart_reply(
            insight_text=payload.text,
            sentiment_score=analysis["sentiment_score"],
        )
        setattr(insight, "ai_reply", ai_reply)
        
        background_tasks.add_task(send_approval_card, insight)
        return insight
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="WB webhook processing failed.") from exc


# БЛОК А3: Ваша логика смены статуса (Исправленная)
@app.patch("/api/v1/insights/{insight_id}/status", tags=["Workflow"])
async def update_insight_status(
    insight_id: UUID,   
    payload: LocalStatusUpdate,  # Используем созданную выше схему
    db: AsyncSession = Depends(get_async_session)
):
    insight = await db.get(Insight, insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Инсайт не найден")

    old_status = insight.status
    
    try:
        # payload.new_status благодаря валидатору уже прилетает большими буквами (например, PENDING)
        new_status_enum = InsightStatus(payload.new_status)
    except ValueError:
        raise HTTPException(status_code=422, detail="Недопустимый статус. Доступные: DRAFT, PENDING, POSTED")

    insight.status = new_status_enum

    # Логирование изменений в Audit Trail
    await log_status_change(
        db,
        insight=insight,
        old_status=old_status,
        new_status=new_status_enum,
        changed_by=payload.changed_by.strip() if payload.changed_by else "mentor",
        comment=payload.comment.strip() if payload.comment and payload.comment.strip() else None,
    )

    await db.commit()
    await db.refresh(insight)
    
    return {
        "message": f"Статус успешно изменен с {old_status.value} на {new_status_enum.value}",
        "insight_id": str(insight.id),
        "current_status": insight.status.value
    }


# БЛОК А3: История логов изменений для ментора
@app.get(
    "/api/v1/insights/{insight_id}/status-logs",
    tags=["Audit"],
    summary="Get status change history for an insight",
)
async def get_status_logs(
    insight_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(StatusLog)
        .where(StatusLog.insight_id == insight_id)
        .order_by(StatusLog.changed_at.desc(), StatusLog.id.desc())
    )
    return result.scalars().all()


# ВАША аналитика 
@app.get("/api/v1/analytics/summary", tags=["Analytics"])
async def get_analytics_summary(db: AsyncSession = Depends(get_async_session)):
    total_result = await db.execute(select(func.count(Insight.id)))
    total_count = total_result.scalar_one()
    
    status_result = await db.execute(
        select(Insight.status, func.count(Insight.id)).group_by(Insight.status)
    )
    status_counts = status_result.all()
    
    stats = {status.value if hasattr(status, 'value') else str(status): count for status, count in status_counts}
    
    return {
        "total_insights": total_count,
        "by_status": stats
    }


@app.get("/api/v1/insights/all-ids", tags=["Development"])
async def get_all_ids(db: AsyncSession = Depends(get_async_session)):
    # Запрос выбирает из базы данных ID всех созданных инсайтов
    result = await db.execute(select(Insight.id))
    # Возвращаем их в виде списка строк для удобного копирования
    return [str(uid) for uid in result.scalars().all()]