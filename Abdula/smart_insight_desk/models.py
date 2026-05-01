from sqlalchemy import Column, String, Float, DateTime
from database import Base
import uuid
from datetime import datetime

class Insight(Base):
    __tablename__ = "insights"

    # Уникальный ID (UUID как просили в ТЗ)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String)
    raw_text = Column(String)
    status = Column(String, default="Draft") # Статус по умолчанию
    created_at = Column(DateTime, default=datetime.utcnow)

    from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database import Base

# 1. Журнал действий (Audit Trail) - обязательное требование ТЗ A3.1
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(Integer, ForeignKey("insights.id"))
    old_status = Column(String)
    new_status = Column(String)
    changed_by = Column(String) # Например, 'Admin_1' или 'Telegram_Bot'
    changed_at = Column(DateTime, default=datetime.utcnow)

# 2. Обратная связь (Feedback) - требование ТЗ A3.1
class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(Integer, ForeignKey("insights.id"))
    comment = Column(String)
    feedback_type = Column(String) # Например, 'Correction' или 'Note'
    created_at = Column(DateTime, default=datetime.utcnow)