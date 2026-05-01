from pydantic import BaseModel, Field
from enum import Enum  # ИМПОРТ ДОЛЖЕН БЫТЬ ТУТ, В САМОМ ВЕРХУ

class ExternalPlatform(str, Enum):
    WB = "wb"
    OZON = "ozon"

# 3. Схема для данных с маркетплейсов (Блок B4)
class ExternalFeedbackDTO(BaseModel):
    remote_id: str
    text: str
    rating: int
    platform: ExternalPlatform
