from pydantic import BaseModel, Field
from enum import Enum  # ИМПОРТ ДОЛЖЕН БЫТЬ ТУТ, В САМОМ ВЕРХУ

# 1. Жестко фиксируем варианты статусов
class InsightStatus(str, Enum):
    DRAFT = "Draft"
    PENDING = "Pending"
    POSTED = "Posted"

# 2. Схема для ручного создания (Swagger)
class InsightCreate(BaseModel):
    source: str
    raw_text: str = Field(..., min_length=1)

# 3. Схема для данных с маркетплейсов (Блок B4)
class ExternalFeedbackDTO(BaseModel):
    remote_id: str
    text: str
    rating: int
    platform: str # 'wb' или 'ozon'

# 4. Схема для обновления статуса (Блок A3)
class StatusUpdate(BaseModel):
    new_status: InsightStatus
    changed_by: str
    comment: str = None