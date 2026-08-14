"""Async HTTP client for the Fantasy Premier League API."""
import httpx

FPL_BASE_URL = "https://fantasy.premierleague.com/api/"
FPL_LOGIN_URL = "https://users.premierleague.com/accounts/login/"


def get_fpl_base_url() -> str:
    return FPL_BASE_URL


class FPLClient:
    def __init__(self, base_url: str = FPL_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout

    def _client(self, cookies: dict | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, cookies=cookies)

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

    async def login(self, email: str, password: str) -> dict:
        """Log in to FPL and return the cookie jar as a serializable dict.

        Raises httpx.HTTPStatusError if credentials are invalid.
        """
        payload = {
            "login": email,
            "password": password,
            "redirect_uri": "https://fantasy.premierleague.com/",
            "app": "plfpl-web",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(FPL_LOGIN_URL, data=payload, headers=headers)
            # FPL returns a 302 redirect on success and 200 on failure.
            if response.status_code in (301, 302, 303, 307, 308):
                return {cookie.name: cookie.value for cookie in client.cookies.jar}
            # Explicitly handle non-redirect as failure.
            if response.status_code >= 400:
                response.raise_for_status()
            raise PermissionError("FPL login failed: invalid credentials or unexpected response")

    async def get_entry_picks(self, entry_id: int, event_id: int, cookies: dict | None = None) -> dict:
        """Fetch picks for a specific gameweek. Requires auth cookies for current/future gameweeks."""
        async with self._client(cookies=cookies) as client:
            response = await client.get(f"{self.base_url}entry/{entry_id}/event/{event_id}/picks/")
            response.raise_for_status()
            return response.json()
