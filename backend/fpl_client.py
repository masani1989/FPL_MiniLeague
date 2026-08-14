"""Async HTTP client for the Fantasy Premier League API."""
import re

import httpx

FPL_BASE_URL = "https://fantasy.premierleague.com/api/"
FPL_LOGIN_URL = "https://users.premierleague.com/accounts/login/"


def get_fpl_base_url() -> str:
    return FPL_BASE_URL


def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """Parse a browser cookie string into a dict for httpx.

    Accepts either a single 'name=value' pair or multiple pairs separated by
    ';'. Whitespace and surrounding quotes are stripped.
    """
    cookies: dict[str, str] = {}
    if not cookie_string:
        return cookies
    # Remove surrounding quotes commonly pasted from browser dev tools.
    cleaned = cookie_string.strip().strip('"').strip("'")
    for pair in cleaned.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name:
            cookies[name] = value
    return cookies


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

    async def get_entry_picks(self, entry_id: int, event_id: int, cookies: dict | None = None) -> dict:
        """Fetch picks for a finished gameweek. No auth required."""
        async with self._client(cookies=cookies) as client:
            response = await client.get(f"{self.base_url}entry/{entry_id}/event/{event_id}/picks/")
            response.raise_for_status()
            return response.json()

    async def get_my_team(self, entry_id: int, cookies: dict | None = None) -> dict:
        """Fetch the latest submitted team for the current/upcoming gameweek.

        Requires a valid FPL session cookie from the browser. Returns a dict
        with 'picks' and 'active_chip' so it can be consumed like
        get_entry_picks.
        """
        if not cookies:
            raise PermissionError("FPL session cookie is required to fetch the latest team.")
        async with self._client(cookies=cookies) as client:
            response = await client.get(f"{self.base_url}my-team/{entry_id}/")
            response.raise_for_status()
            data = response.json()
        # my-team returns picks under a different shape; normalize it.
        picks = data.get("picks", [])
        return {
            "picks": picks,
            "active_chip": data.get("active_chip"),
            "entry_history": data.get("entry_history", {}),
        }

    @staticmethod
    def parse_session_cookie(cookie_string: str) -> dict[str, str]:
        """Parse a pasted browser cookie string into a dict for httpx."""
        return parse_cookie_string(cookie_string)
