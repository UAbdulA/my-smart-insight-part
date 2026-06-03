import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from main import app  # Импортируем наше FastAPI приложение

@pytest.mark.asyncio
async def test_analytics_summary_endpoint():
    """Тест проверяет, что роут аналитики доступен и возвращает структуру"""
    # Для новых версий httpx передаем приложение через транспорт
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    assert "total_insights" in response.json()
    assert "by_status" in response.json()

@pytest.mark.asyncio
async def test_update_status_insight_not_found():
    """Тест проверяет, что при несуществующем ID роут смены статуса вернет 404"""
    random_uuid = str(uuid4())
    payload = {
        "new_status": "pending",
        "changed_by": "test_bot",
        "comment": "Тестовый комментарий"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(f"/api/v1/insights/{random_uuid}/status", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Инсайт не найден"

@pytest.mark.asyncio
async def test_get_all_ids_endpoint():
    """Тест проверяет работоспособность нашего починенного роута all-ids"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/insights/all-ids")
    assert response.status_code == 200
    assert isinstance(response.json(), list)