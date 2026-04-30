import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class OzonConnector:
    def __init__(self, client_id: str, api_key: str):
        self.headers = {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }
        self.base_url = "https://api-seller.ozon.ru"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_reviews(self):
        payload = {"filter": {"with_score": [1, 2, 3]}, "limit": 10}
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/v3/rating/review/list", headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()