from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database
from connectors.wb_client import WBConnector
from connectors.ozon_client import OzonConnector

# 1. Сначала создаем таблицы в базе
models.Base.metadata.create_all(bind=database.engine)

# 2. Потом запускаем само приложение (одной строкой)
app = FastAPI(title="Smart Insight Desk")

# Главная страница
@app.get("/")
async def home():
    return {"status": "Работает!", "info": "Зайди на /docs для теста"}

# Тестовый роут (используем уже готовую схему InsightCreate)
@app.post("/test")
async def create_test(data: schemas.InsightCreate, db: Session = Depends(database.get_db)):
    new_insight = models.Insight(source=data.source, raw_text=data.raw_text)
    db.add(new_insight)
    db.commit()
    db.refresh(new_insight)
    return {"message": f"Получено от {data.source}", "id": new_insight.id}
 
    # БЛОК А3: Смена статуса и аудит
@app.patch("/insights/{insight_id}/status")
async def update_insight_status(
    insight_id: str,   
    payload: schemas.StatusUpdate, 
    db: Session = Depends(database.get_db)
):
    # 1. Ищем инсайт
    insight = db.query(models.Insight).filter(models.Insight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Инсайт не найден")

    # 2. Записываем старый статус перед изменением
    old_status = insight.status

    # 3. Обновляем статус
    insight.status = payload.new_status

    # 4. Пишем в Журнал действий (Audit Trail)
    log = models.AuditLog(
        insight_id=insight_id,
        old_status=old_status,
        new_status=payload.new_status,
        changed_by=payload.changed_by
    )
    db.add(log)

    # 5. Если есть комментарий, пишем в таблицу Feedback
    if payload.comment:
        new_feedback = models.Feedback(
            insight_id=insight_id,
            comment=payload.comment,
            feedback_type="Correction" # Или payload.author, если добавил в схему
        )
        db.add(new_feedback)

    db.commit()
    return {"message": f"Статус изменен с {old_status} на {payload.new_status}"}

# Добавь это в конец main.py, чтобы увидеть все ID
@app.get("/insights/all")
def get_all_ids(db: Session = Depends(database.get_db)):
    return db.query(models.Insight.id).all()

from sqlalchemy import func

@app.get("/analytics/summary")
def get_analytics(db: Session = Depends(database.get_db)):
    # 1. Считаем общее количество инсайтов
    total_count = db.query(models.Insight).count()
    
    # 2. Считаем количество по каждому статусу (группировка)
    status_counts = db.query(
        models.Insight.status, 
        func.count(models.Insight.id)
    ).group_by(models.Insight.status).all()
    
    # Превращаем результат в удобный словарь { "Draft": 5, "Pending": 2 }
    stats = {status: count for status, count in status_counts}
    
    return {
        "total_insights": total_count,
        "by_status": stats
    }