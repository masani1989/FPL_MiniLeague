"""Async HTTP client for the Fantasy Premier League API."""
import httpx

FPL_BASE_URL = "https://fantasy.premierleague.com/api/"


def get_fpl_base_url() -> str:
    return FPL_BASE_URL


class FPLClient:
    def __init__(self, base_url: str = FPL_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout)

    async def get_bootstrap_static(self) -> dict:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}bootstrap-static/")
            response.raise_for_status()
            return response.json()

    async def get_entry_history(self, entry_id: int) -> dict:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}entry/{entry_id}/history/")
            response.raise_for_status()
            return response.json()

    async def get_fixtures(self) -> list[dict]:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}fixtures/")
            response.raise_for_status()
            return response.json()

    async def get_player_summary(self, player_id: int) -> dict:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}element-summary/{player_id}/")
            response.raise_for_status()
            return response.json()

    async def get_league_standings(self, league_id: int) -> dict:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}leagues-classic/{league_id}/standings/")
            response.raise_for_status()
            return response.json()
