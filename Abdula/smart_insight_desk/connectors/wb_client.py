import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class WBConnector:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://feedbacks-api.wildberries.ru"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_feedbacks(self):
        headers = {"Authorization": self.token}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/feedbacks?isAnswered=false", headers=headers)
            response.raise_for_status() 
            return response.json()