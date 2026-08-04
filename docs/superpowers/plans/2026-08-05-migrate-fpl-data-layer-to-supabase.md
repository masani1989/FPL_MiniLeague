# Migrate FPL Data Layer from Google Sheets to Supabase

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. If you use a worktree, create it via `superpowers:using-git-worktrees` at execution time.

**Goal:** Replace Google Sheets with Supabase as the persistence layer for gameweek, monthly, overall and refresh-timestamp data, while keeping the Streamlit UI and FPL API integration behavior unchanged.

**Architecture:** Introduce a thin Supabase client wrapper (`Utils/supabase_conn.py`) that exposes the same-shaped DataFrames the views already consume. Model reference data (`seasons`, `league`, `managers`, `gameweek`) relationally so the statistical tables (`overall_standings`, `gameweek_results`, `monthly_results`) reference them via foreign keys while still denormalizing the player name for display. Refactor `Utils/standings.py` and `Utils/refreshData.py` to call the wrapper instead of `Utils/gsheet_conn.py`. Provide a one-time migration script that copies existing sheet rows into Supabase. Add lightweight unit tests with a mocked Supabase client.

**Tech Stack:** Python 3.11, Streamlit 1.37.1, pandas 1.5.3, Supabase (PostgreSQL via `supabase-py`), pytest.

## Global Constraints

- Python version: **3.11** (matches existing `venv`).
- Streamlit version: **==1.37.1** (do not bump).
- pandas version: **==1.5.3** (do not bump).
- Phase 1 scope: **data-layer swap only** — no new UI features, no schema redesign for future phases.
- DataFrames returned by the new layer must have the **same column names and dtypes** as the current Google Sheets loader, so views need minimal changes.
- Secrets stay in `.streamlit/secrets.toml`; a `.streamlit/secrets.toml.example` template must be maintained.
- Supabase credentials use the **service role key** for server-side refresh operations.
- Reference tables (`seasons`, `league`, `managers`, `gameweek`) are populated automatically from the FPL API during refresh and migration.
- Player names are denormalized into statistical tables so views do not need joins.
- **Season id and FPL league id are parameterized** in `Utils/config.py` and read from environment variables / secrets, with sensible defaults for Fantasy Kings 2025-26 (`2025-26`, `282978`).
- All code changes are committed after each independently testable task.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Add `supabase-py` and `pytest` dependencies. |
| `.streamlit/secrets.toml.example` | Template showing required Supabase + legacy Google Sheets sections + `app` section. |
| `Utils/config.py` | Single source of truth for `SEASON_ID`, `FPL_LEAGUE_ID`, `LEAGUE_NAME` and derived `LEAGUE_RECORD_ID`. |
| `schema.sql` | PostgreSQL DDL for `seasons`, `league`, `managers`, `gameweek`, `overall_standings`, `gameweek_results`, `monthly_results`, `data_refresh_log`. |
| `Utils/supabase_conn.py` | Thin wrapper around `supabase-py`: client init, reference-table sync, read helpers, upsert/delete helpers. Reads season/league config from `Utils.config`. |
| `Utils/standings.py` | Replace Google Sheets reads with `Utils.supabase_conn` reads; keep winnings calculations. |
| `Utils/refreshData.py` | Replace Google Sheets writes with Supabase sync + upserts; populate reference tables before writing stats. Uses `Utils.config`. |
| `views/about_me.py` | Replace `gs.data_load('DataDate', ...)` with `supabase_conn.load_data_date()`. |
| `views/analytics.py` | Replace `gs.data_load('Gameweek', ...)` with `supabase_conn.load_gameweek()`. |
| `views/minileague.py` | Remove unused `gs` import; no other change. |
| `scripts/migrate_from_gsheets.py` | One-time script: read all Google Sheets, sync reference tables, upsert stats, log refresh. Uses `Utils.config`. |
| `tests/conftest.py` | Shared pytest fixtures: mock Supabase client, sample DataFrames. |
| `tests/test_supabase_conn.py` | Unit tests for reference sync and read helpers using the mock client. |
| `tests/test_standings.py` | Unit tests for `data_refresh` and `winnings_data`. |
| `tests/test_refresh_data.py` | Unit tests for the Supabase refresh pipeline. |
| `tests/test_config.py` | Unit tests verifying config defaults and environment overrides. |
| `README.md` | Update setup instructions: Supabase project, schema, secrets, migration, config overrides. |

---

### Task 1: Add Supabase and Test Dependencies

**Files:**
- Modify: `requirements.txt:1-14`
- Test: `pytest --version`

**Interfaces:**
- Consumes: None.
- Produces: `supabase` and `pytest` importable in the environment.

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append two lines to `requirements.txt`:

```text
supabase>=2.5.0,<3.0.0
pytest>=8.0.0,<9.0.0
```

The full file should look like:

```text
pandas==1.5.3
altair==5.3.0
matplotlib==3.8.2
numpy==1.25.0
plotly==5.23.0
plotly-express==0.4.1
pyarrow==17.0.0
requests==2.31.0
requests-oauthlib==2.0.0
st-gsheets-connection
streamlit==1.37.1
toml==0.10.2
oauth2client==4.1.3
supabase>=2.5.0,<3.0.0
pytest>=8.0.0,<9.0.0
```

- [ ] **Step 2: Install dependencies and verify pytest**

Run:

```bash
cd "/Users/himanshu/Pet Projects/FPL"
source venv/bin/activate
pip install -r requirements.txt
pytest --version
```

Expected: `pytest` prints a version >= 8.0.0 and `supabase` is importable:

```bash
python -c "import supabase; print(supabase.__version__)"
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add supabase-py and pytest for data layer migration"
```

---

### Task 2: Add Parameterized Config Module

**Files:**
- Create: `Utils/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: environment variables `FPL_SEASON_ID`, `FPL_LEAGUE_ID`, `FPL_LEAGUE_NAME` and Streamlit secrets `app.season_id`, `app.fpl_league_id`, `app.league_name`.
- Produces:
  - `SEASON_ID: str`
  - `FPL_LEAGUE_ID: int`
  - `LEAGUE_NAME: str`
  - `LEAGUE_RECORD_ID: int` (used as the internal `league.id` PK to keep the wrapper simple)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest

import Utils.config as cfg


def test_default_config_values():
    # Ensure a clean env for this test
    for key in ("FPL_SEASON_ID", "FPL_LEAGUE_ID", "FPL_LEAGUE_NAME"):
        os.environ.pop(key, None)
    # Re-import to pick up defaults (monkeypatch import in real run)
    from importlib import reload
    reloaded = reload(cfg)
    assert reloaded.SEASON_ID == "2025-26"
    assert reloaded.FPL_LEAGUE_ID == 282978
    assert reloaded.LEAGUE_NAME == "Fantasy Kings"
    assert reloaded.LEAGUE_RECORD_ID == 282978


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("FPL_SEASON_ID", "2026-27")
    monkeypatch.setenv("FPL_LEAGUE_ID", "999999")
    monkeypatch.setenv("FPL_LEAGUE_NAME", "Other League")
    from importlib import reload
    reloaded = reload(cfg)
    assert reloaded.SEASON_ID == "2026-27"
    assert reloaded.FPL_LEAGUE_ID == 999999
    assert reloaded.LEAGUE_NAME == "Other League"
    assert reloaded.LEAGUE_RECORD_ID == 999999
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_config.py::test_default_config_values -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'Utils.config'`.

- [ ] **Step 3: Implement `Utils/config.py`**

Create `Utils/config.py`:

```python
"""Central, parameterized configuration for the FPL app.

Values are read from Streamlit secrets first (so production can override them
without code changes), then from environment variables, then fall back to
sensible defaults for Fantasy Kings 2025-26.
"""
import os

import streamlit as st


def _get_str(key: str, default: str) -> str:
    try:
        return st.secrets["app"][key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    raw = _get_str(key, str(default))
    return int(raw)


SEASON_ID = _get_str("season_id", "2025-26")
FPL_LEAGUE_ID = _get_int("fpl_league_id", 282978)
LEAGUE_NAME = _get_str("league_name", "Fantasy Kings")

# For Phase 1 the internal Supabase league.id is the same as the FPL league id.
# This removes the need to look it up every time we write stats.
LEAGUE_RECORD_ID = FPL_LEAGUE_ID
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Utils/config.py tests/test_config.py
git commit -m "feat: add parameterized config for season and league ids"
```

---

### Task 3: Configure Supabase Secrets

**Files:**
- Modify: `.streamlit/secrets.toml.example` (created in Task 1; now add `[app]` section)
- Test: `python -c "import toml; toml.load('.streamlit/secrets.toml.example')"`

**Interfaces:**
- Consumes: None.
- Produces: A documented secrets template with `[app]`, `[supabase]` and legacy Google Sheets sections.

- [ ] **Step 1: Update the secrets template**

Update `.streamlit/secrets.toml.example` to include the new `[app]` section:

```toml
[app]
season_id = "2025-26"
fpl_league_id = "282978"
league_name = "Fantasy Kings"

[connections.gsheets]
# Legacy Google Sheets connection. Keep until migration is complete and verified.
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
worksheet = "<worksheet-gid-or-folder-id>"
type = "service_account"
project_id = "your-gsheets-project"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."

[google_sheets]
# Legacy credentials string used by Utils/refreshData.py via gspread.
credentials = """
{
  "type": "service_account",
  ...
}
"""

[supabase]
url = "https://your-project-ref.supabase.co"
key = "your-service-role-key"
```

- [ ] **Step 2: Verify the template is valid TOML**

Run:

```bash
cd "/Users/himanshu/Pet Projects/FPL"
python -c "import toml; toml.load('.streamlit/secrets.toml.example')"
```

Expected: command exits with code 0 and no output.

- [ ] **Step 3: Commit**

```bash
git add .streamlit/secrets.toml.example
git commit -m "chore: add app config section to secrets template"
```

---

### Task 4: Create Relational Supabase Database Schema

**Files:**
- Create: `schema.sql`
- Test: validate SQL file is non-empty; manual validation in Supabase SQL Editor required before running app.

**Interfaces:**
- Consumes: None.
- Produces: SQL DDL that creates reference tables and statistical tables with foreign keys and unique constraints required for upserts.

- [ ] **Step 1: Write `schema.sql`**

Create `schema.sql`:

```sql
-- FPL Fantasy Kings - Phase 1 Supabase schema
-- Run this in the Supabase SQL Editor before running the app or migration.

-- Seasons lookup. One active season is sufficient for Phase 1.
create table if not exists seasons (
    id text primary key,
    name text not null,
    is_active boolean default false
);

insert into seasons (id, name, is_active)
values ('2025-26', 'Fantasy Kings 2025-26', true)
on conflict (id) do nothing;

-- Mini-league reference table.
create table if not exists league (
    id int primary key,
    fpl_league_id int not null,
    name text not null,
    season_id text not null references seasons(id),
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_league_id, season_id)
);

-- Manager reference table. One row per FPL entry per league.
create table if not exists managers (
    id serial primary key,
    fpl_entry_id int not null,
    league_id int not null references league(id),
    player_name text not null,
    team_name text not null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_entry_id, league_id)
);

-- Gameweek reference table. One row per FPL gameweek per season.
create table if not exists gameweek (
    id serial primary key,
    fpl_gameweek_id int not null,
    season_id text not null references seasons(id),
    name text not null,
    deadline_time timestamp with time zone,
    finished boolean default false,
    is_current boolean default false,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_gameweek_id, season_id)
);

-- Overall mini-league standings (replaces the 'Overall' worksheet).
create table if not exists overall_standings (
    id serial primary key,
    manager_id int not null references managers(id),
    player_name text not null,
    rank int not null,
    points int not null,
    last_rank int,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, season_id)
);

-- Per-gameweek results (replaces the 'Gameweek' worksheet).
create table if not exists gameweek_results (
    id serial primary key,
    manager_id int not null references managers(id),
    gameweek_id int not null references gameweek(id),
    player_name text not null,
    gross int not null,
    transfer int not null,
    points int not null,
    rank int,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, gameweek_id, season_id)
);

-- Monthly aggregated results (replaces the 'Monthly' worksheet).
create table if not exists monthly_results (
    id serial primary key,
    manager_id int not null references managers(id),
    player_name text not null,
    points int not null,
    rank int,
    month text not null,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, month, season_id)
);

-- Refresh audit log (replaces the 'DataDate' worksheet).
create table if not exists data_refresh_log (
    id serial primary key,
    refreshed_at timestamp with time zone default now(),
    gameweek_id int references gameweek(id),
    status text,
    notes text
);

-- Index for the latest refresh lookup used by the home page.
create index if not exists idx_data_refresh_log_refreshed_at
    on data_refresh_log (refreshed_at desc);
```

- [ ] **Step 2: Validate the SQL file exists and is non-empty**

Run:

```bash
cd "/Users/himanshu/Pet Projects/FPL"
test -s schema.sql && echo "schema.sql is present and non-empty"
```

Expected: prints confirmation.

- [ ] **Step 3: Commit**

```bash
git add schema.sql
git commit -m "chore: add relational Supabase schema with league, managers, gameweek and stats tables"
```

---

### Task 5: Create Supabase Data Access Layer

**Files:**
- Create: `Utils/supabase_conn.py`
- Test: `tests/test_supabase_conn.py`

**Interfaces:**
- Consumes: `st.secrets["supabase"]["url"]`, `st.secrets["supabase"]["key"]`, `Utils.config.SEASON_ID`, `Utils.config.LEAGUE_RECORD_ID`, `Utils.config.LEAGUE_NAME`.
- Produces:
  - `get_client() -> Client`
  - `sync_league(season_id: str, fpl_league_id: int, league_name: str) -> int` returns internal `league.id`
  - `sync_managers(league_id: int, managers_df: pd.DataFrame) -> dict[int, int]` maps `fpl_entry_id` to `manager_id`. Expected input columns: `['PlayerId', 'Player', 'Team']`.
  - `sync_gameweeks(season_id: str, gameweeks_df: pd.DataFrame) -> dict[int, int]` maps `fpl_gameweek_id` to `gameweek.id`. Expected input columns: `['FplGameweekId', 'Name', 'DeadlineTime', 'Finished', 'IsCurrent']`.
  - `load_overall(season_id: str) -> pd.DataFrame` with columns `['Rank', 'Player', 'Points', 'Last_Rank']`
  - `load_gameweek(season_id: str) -> pd.DataFrame` with columns `['Player', 'Gross', 'Transfer', 'Points', 'Rank', 'Gameweek']`
  - `load_gameweek_for_refresh(season_id: str) -> pd.DataFrame` with columns `['PlayerId', 'Player', 'Points', 'Gameweek']`
  - `load_monthly(season_id: str) -> pd.DataFrame` with columns `['Player', 'Points', 'Rank', 'Month']`
  - `load_data_date() -> pd.DataFrame` with one row and column `['DataAsOf']` formatted as `'%m/%d/%Y %H:%M:%S'`
  - `upsert_overall(df, manager_id_map, season_id)` accepts DataFrame with columns `['PlayerId', 'Player', 'Rank', 'Points', 'Last_Rank']`
  - `upsert_gameweek(df, manager_id_map, gameweek_id_map, season_id)` accepts DataFrame with columns `['PlayerId', 'Player', 'Gross', 'Transfer', 'Points', 'Rank', 'Gameweek']`
  - `upsert_monthly(df, manager_id_map, season_id)` accepts DataFrame with columns `['PlayerId', 'Player', 'Points', 'Rank', 'Month']`
  - `delete_gameweek(fpl_gameweek: int, gameweek_id_map: dict[int, int])`
  - `log_data_refresh(gameweek_id=None, status='success', notes='')`

- [ ] **Step 1: Write the failing test for `sync_league`**

Create `tests/test_supabase_conn.py`:

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock

from Utils import supabase_conn


class FakeResponse:
    def __init__(self, data):
        self.data = data


def _make_mock_client(upsert_response=None):
    """Return a mock Supabase client that records upserts and returns canned select data."""
    client = MagicMock()

    # Store call args for assertions.
    client._upserts = []
    client._selects = {}

    def upsert_side_effect(records, on_conflict=None):
        client._upserts.append((records, on_conflict))
        return MagicMock(execute=MagicMock(return_value=FakeResponse(records)))

    def table_side_effect(name):
        chain = MagicMock()

        def select_executor():
            data = client._selects.get(name, [])
            return FakeResponse(data)

        select_chain = MagicMock()
        select_chain.execute = select_executor
        chain.select.return_value = select_chain

        # Upsert chain.
        upsert_chain = MagicMock()
        upsert_chain.upsert.side_effect = upsert_side_effect
        chain.upsert.return_value = upsert_chain

        # Insert chain.
        insert_chain = MagicMock()
        insert_chain.execute.return_value = FakeResponse([])
        chain.insert.return_value = insert_chain

        # Delete chain.
        delete_chain = MagicMock()
        delete_chain.eq.return_value.execute.return_value = FakeResponse([])
        chain.delete.return_value = delete_chain

        return chain

    client.table.side_effect = table_side_effect
    return client


def test_sync_league_inserts_and_returns_id(monkeypatch):
    client = _make_mock_client()
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    league_id = supabase_conn.sync_league("2025-26", 282978, "Fantasy Kings")

    assert league_id == 282978
    assert len(client._upserts) == 1
    records, on_conflict = client._upserts[0]
    assert records[0]["fpl_league_id"] == 282978
    assert records[0]["name"] == "Fantasy Kings"
    assert records[0]["season_id"] == "2025-26"
    assert on_conflict == "fpl_league_id,season_id"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_supabase_conn.py::test_sync_league_inserts_and_returns_id -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'Utils.supabase_conn'`.

- [ ] **Step 3: Implement `Utils/supabase_conn.py`**

Create `Utils/supabase_conn.py`:

```python
import os
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from Utils import config


def _get_credentials() -> dict[str, str]:
    """Read Supabase credentials from Streamlit secrets or environment variables."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except (KeyError, FileNotFoundError):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase URL and key are missing. Check .streamlit/secrets.toml or env vars.")
    return {"url": url, "key": key}


@st.cache_resource
def get_client() -> Client:
    """Create and cache a Supabase client."""
    creds = _get_credentials()
    return create_client(creds["url"], creds["key"])


def _fetch_table(table_name: str, season_id: str | None = None) -> pd.DataFrame:
    """Fetch rows from a Supabase table, optionally filtered by season_id."""
    client = get_client()
    query = client.table(table_name).select("*")
    if season_id is not None:
        query = query.eq("season_id", season_id)
    response = query.execute()
    return pd.DataFrame(response.data)


def sync_league(season_id: str, fpl_league_id: int, league_name: str) -> int:
    """Upsert the league record and return the internal league id.

    For Phase 1 we use the FPL league id as the internal primary key to keep the
    wrapper simple.
    """
    client = get_client()
    record = {
        "id": fpl_league_id,
        "fpl_league_id": fpl_league_id,
        "name": league_name,
        "season_id": season_id,
    }
    client.table("league").upsert(record, on_conflict="fpl_league_id,season_id").execute()
    return fpl_league_id


def sync_managers(league_id: int, managers_df: pd.DataFrame) -> dict[int, int]:
    """Upsert managers for a league and return {fpl_entry_id: manager_id}.

    Expected input columns: PlayerId, Player, Team.
    """
    if managers_df.empty:
        return {}

    client = get_client()
    records = []
    for _, row in managers_df.iterrows():
        records.append({
            "fpl_entry_id": int(row["PlayerId"]),
            "league_id": league_id,
            "player_name": str(row["Player"]),
            "team_name": str(row["Team"]),
        })

    response = client.table("managers").upsert(records, on_conflict="fpl_entry_id,league_id").execute()

    mapping = {}
    for record in response.data:
        mapping[int(record["fpl_entry_id"])] = int(record["id"])
    return mapping


def sync_gameweeks(season_id: str, gameweeks_df: pd.DataFrame) -> dict[int, int]:
    """Upsert gameweeks for a season and return {fpl_gameweek_id: gameweek_id}.

    Expected input columns: FplGameweekId, Name, DeadlineTime, Finished, IsCurrent.
    """
    if gameweeks_df.empty:
        return {}

    client = get_client()
    records = []
    for _, row in gameweeks_df.iterrows():
        deadline = row.get("DeadlineTime")
        if pd.isna(deadline):
            deadline = None
        records.append({
            "fpl_gameweek_id": int(row["FplGameweekId"]),
            "season_id": season_id,
            "name": str(row["Name"]),
            "deadline_time": deadline,
            "finished": bool(row["Finished"]),
            "is_current": bool(row["IsCurrent"]),
        })

    response = client.table("gameweek").upsert(records, on_conflict="fpl_gameweek_id,season_id").execute()

    mapping = {}
    for record in response.data:
        mapping[int(record["fpl_gameweek_id"])] = int(record["id"])
    return mapping


@st.cache_data(ttl=300)
def load_overall(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load overall standings in the shape the UI expects."""
    df = _fetch_table("overall_standings", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Rank", "Player", "Points", "Last_Rank"])

    df = df[["rank", "player_name", "points", "last_rank"]].rename(
        columns={
            "rank": "Rank",
            "player_name": "Player",
            "points": "Points",
            "last_rank": "Last_Rank",
        }
    )
    df = df[["Rank", "Player", "Points", "Last_Rank"]]
    return df.astype({"Rank": "int64", "Last_Rank": "int64", "Points": "int64"})


@st.cache_data(ttl=300)
def load_gameweek(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load per-gameweek results in the shape the UI expects."""
    df = _fetch_table("gameweek_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"])

    df = df[["player_name", "gross", "transfer", "points", "rank", "gameweek_id"]].rename(
        columns={
            "player_name": "Player",
            "gross": "Gross",
            "transfer": "Transfer",
            "points": "Points",
            "rank": "Rank",
            "gameweek_id": "Gameweek",
        }
    )
    df = df[["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]]
    return df.astype(
        {
            "Player": "object",
            "Gross": "int64",
            "Transfer": "int64",
            "Points": "int64",
            "Rank": "int64",
            "Gameweek": "int64",
        }
    )


@st.cache_data(ttl=300)
def load_gameweek_for_refresh(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load gameweek results with manager FPL id for the refresh pipeline."""
    df = _fetch_table("gameweek_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Points", "Gameweek"])

    managers_df = _fetch_table("managers")
    if managers_df.empty:
        return pd.DataFrame(columns=["PlayerId", "Player", "Points", "Gameweek"])

    merged = df.merge(
        managers_df[["id", "fpl_entry_id", "player_name"]],
        left_on="manager_id",
        right_on="id",
    )
    merged = merged[["fpl_entry_id", "player_name", "points", "gameweek_id"]].rename(
        columns={
            "fpl_entry_id": "PlayerId",
            "player_name": "Player",
            "points": "Points",
            "gameweek_id": "Gameweek",
        }
    )
    return merged.astype({"PlayerId": "int64", "Points": "int64", "Gameweek": "int64"})


@st.cache_data(ttl=300)
def load_monthly(season_id: str = config.SEASON_ID) -> pd.DataFrame:
    """Load monthly results in the shape the UI expects."""
    df = _fetch_table("monthly_results", season_id)
    if df.empty:
        return pd.DataFrame(columns=["Player", "Points", "Rank", "Month"])

    df = df[["player_name", "points", "rank", "month"]].rename(
        columns={
            "player_name": "Player",
            "points": "Points",
            "rank": "Rank",
            "month": "Month",
        }
    )
    df = df[["Player", "Points", "Rank", "Month"]]
    return df.astype({"Player": "object", "Points": "int64", "Rank": "int64", "Month": "object"})


@st.cache_data(ttl=60)
def load_data_date() -> pd.DataFrame:
    """Return the most recent refresh timestamp formatted like the old DataDate sheet."""
    client = get_client()
    response = (
        client.table("data_refresh_log")
        .select("*")
        .order("refreshed_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        fallback = datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")
        return pd.DataFrame({"DataAsOf": [fallback]})

    refreshed_at = response.data[0]["refreshed_at"]
    dt = pd.to_datetime(refreshed_at)
    return pd.DataFrame({"DataAsOf": [dt.strftime("%m/%d/%Y %H:%M:%S")]})


def _prepare_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-ready records, replacing NaNs with None."""
    cleaned = df.copy()
    for col in cleaned.columns:
        if cleaned[col].dtype.kind in "bifc":
            cleaned[col] = cleaned[col].replace({pd.NA: None}).where(
                cleaned[col].notna(), None
            )
    return cleaned.to_dict(orient="records")


def upsert_overall(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert overall standings.

    Expected columns: PlayerId, Player, Rank, Points, Last_Rank.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Rank": "rank",
            "Points": "points",
            "Last_Rank": "last_rank",
        }
    )
    mapped = mapped[["manager_id", "player_name", "rank", "points", "last_rank"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("overall_standings").upsert(records, on_conflict="manager_id,season_id").execute()


def upsert_gameweek(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    gameweek_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert gameweek results.

    Expected columns: PlayerId, Player, Gross, Transfer, Points, Rank, Gameweek.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped["gameweek_id"] = mapped["Gameweek"].map(gameweek_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Gross": "gross",
            "Transfer": "transfer",
            "Points": "points",
            "Rank": "rank",
        }
    )
    mapped = mapped[["manager_id", "gameweek_id", "player_name", "gross", "transfer", "points", "rank"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("gameweek_results").upsert(records, on_conflict="manager_id,gameweek_id,season_id").execute()


def upsert_monthly(
    df: pd.DataFrame,
    manager_id_map: dict[int, int],
    season_id: str = config.SEASON_ID,
) -> None:
    """Upsert monthly results.

    Expected columns: PlayerId, Player, Points, Rank, Month.
    """
    mapped = df.copy()
    mapped["manager_id"] = mapped["PlayerId"].map(manager_id_map)
    mapped = mapped.rename(
        columns={
            "Player": "player_name",
            "Points": "points",
            "Rank": "rank",
            "Month": "month",
        }
    )
    mapped = mapped[["manager_id", "player_name", "points", "rank", "month"]]
    mapped["season_id"] = season_id

    records = _prepare_records(mapped)
    client = get_client()
    client.table("monthly_results").upsert(records, on_conflict="manager_id,month,season_id").execute()


def delete_gameweek(fpl_gameweek: int, gameweek_id_map: dict[int, int]) -> None:
    """Delete all rows for a specific FPL gameweek in the active season."""
    gameweek_id = gameweek_id_map.get(fpl_gameweek)
    if gameweek_id is None:
        return

    client = get_client()
    (
        client.table("gameweek_results")
        .delete()
        .eq("gameweek_id", gameweek_id)
        .execute()
    )


def log_data_refresh(
    gameweek_id: int | None = None,
    status: str = "success",
    notes: str = "",
) -> None:
    """Insert a new refresh audit row."""
    record = {
        "gameweek_id": gameweek_id,
        "status": status,
        "notes": notes,
    }
    client = get_client()
    client.table("data_refresh_log").insert(record).execute()
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_supabase_conn.py::test_sync_league_inserts_and_returns_id -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Utils/supabase_conn.py tests/test_supabase_conn.py
git commit -m "feat: add parameterized Supabase data access layer with relational reference tables"
```

---

### Task 6: Migrate Standings Read Path

**Files:**
- Modify: `Utils/standings.py:1-49`
- Test: `tests/test_standings.py`

**Interfaces:**
- Consumes: `supabase_conn.load_overall()`, `supabase_conn.load_gameweek()`, `supabase_conn.load_monthly()`. All default to `config.SEASON_ID`.
- Produces: `data_refresh()` returns `(ovr_data, gw_data, mn_data)` with unchanged column shapes. `winnings_data(gw_data, mn_data)` unchanged.

- [ ] **Step 1: Write the failing test for `data_refresh`**

Create `tests/test_standings.py`:

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import Utils.standings as stg


def test_data_refresh_returns_three_expected_dataframes():
    ovr = pd.DataFrame({
        "Rank": [1, 2],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Last_Rank": [2, 1],
    })
    gw = pd.DataFrame({
        "Player": ["A B"],
        "Gross": [50],
        "Transfer": [4],
        "Points": [46],
        "Rank": [1],
        "Gameweek": [1],
    })
    mn = pd.DataFrame({
        "Player": ["A B"],
        "Points": [46],
        "Rank": [1],
        "Month": ["August"],
    })

    with patch("Utils.standings.db.load_overall", return_value=ovr), \
         patch("Utils.standings.db.load_gameweek", return_value=gw), \
         patch("Utils.standings.db.load_monthly", return_value=mn):
        result = stg.data_refresh()

    assert len(result) == 3
    assert list(result[0].columns) == ["Rank", "Player", "Points", "Last_Rank"]
    assert list(result[1].columns) == ["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]
    assert list(result[2].columns) == ["Player", "Points", "Rank", "Month"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_standings.py::test_data_refresh_returns_three_expected_dataframes -v
```

Expected: FAIL because `Utils.standings.db` is not yet imported.

- [ ] **Step 3: Update `Utils/standings.py` to use Supabase**

Replace the top of `Utils/standings.py`:

```python
import streamlit as st
import pandas as pd
import Utils.supabase_conn as db


@st.cache_data()
def data_refresh():
    """
    Function to refresh data from Supabase containing the GW, Monthly and Overall standings and points.
    :return: tuple of (ovr_data, gw_data, mn_data)
    """
    ovr_data = db.load_overall()
    gw_data = db.load_gameweek()
    mn_data = db.load_monthly()
    return ovr_data, gw_data, mn_data
```

The rest of the file (`winnings_data`) remains unchanged.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_standings.py::test_data_refresh_returns_three_expected_dataframes -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Utils/standings.py tests/test_standings.py
git commit -m "refactor: read standings from Supabase instead of Google Sheets"
```

---

### Task 7: Migrate Refresh Data Write Path

**Files:**
- Modify: `Utils/refreshData.py:1-120`
- Test: `tests/test_refresh_data.py`

**Interfaces:**
- Consumes:
  - `config.SEASON_ID`, `config.FPL_LEAGUE_ID`, `config.LEAGUE_NAME`, `config.LEAGUE_RECORD_ID`
  - `supabase_conn.sync_league(...)`, `supabase_conn.sync_managers(...)`, `supabase_conn.sync_gameweeks(...)`
  - `supabase_conn.upsert_overall(df, manager_id_map, season_id)`, `supabase_conn.upsert_gameweek(df, manager_id_map, gameweek_id_map, season_id)`, `supabase_conn.upsert_monthly(df, manager_id_map, season_id)`
  - `supabase_conn.delete_gameweek(fpl_gameweek, gameweek_id_map)`, `supabase_conn.load_gameweek_for_refresh()`
  - `supabase_conn.log_data_refresh(...)`
- Produces: `refGw()`, `refMnth(g)`, `refOverall()` update reference tables first, then write stats to Supabase for the configured season/league.

- [ ] **Step 1: Write the failing test for `refOverall`**

Create `tests/test_refresh_data.py`:

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import Utils.refreshData as rd


def test_refOverall_upserts_standings_to_supabase():
    standings = pd.DataFrame({
        "PlayerId": [777321, 999999],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Rank": [1, 2],
        "Last_Rank": [2, 1],
    })
    manager_map = {777321: 1, 999999: 2}

    with patch("Utils.refreshData.lg.get_league_standings", return_value=standings), \
         patch("Utils.refreshData._ensure_reference_tables", return_value=(282978, manager_map, {1: 101})), \
         patch("Utils.refreshData.db.upsert_overall") as mock_upsert:
        rd.refOverall()

    mock_upsert.assert_called_once()
    passed_df, passed_map, passed_season = mock_upsert.call_args[0]
    assert list(passed_df.columns) == ["PlayerId", "Player", "Points", "Rank", "Last_Rank"]
    assert passed_map == manager_map
    assert passed_season == "2025-26"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_refresh_data.py::test_refOverall_upserts_standings_to_supabase -v
```

Expected: FAIL because `Utils.refreshData._ensure_reference_tables` and `Utils.refreshData.db` are not defined.

- [ ] **Step 3: Update `Utils/refreshData.py`**

Replace the imports and helpers in `Utils/refreshData.py`:

```python
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Utils.league import *
import Utils.gameweek as gwk
import Utils.supabase_conn as db
from Utils import config
import pandas as pd
import argparse


def _ensure_reference_tables():
    """Sync league, managers and gameweeks before writing stats.

    Returns (league_id, manager_id_map, gameweek_id_map).
    """
    lg = league(config.FPL_LEAGUE_ID)
    league_id = db.sync_league(config.SEASON_ID, config.FPL_LEAGUE_ID, config.LEAGUE_NAME)

    players = lg.get_league_players()
    players_df = pd.DataFrame.from_records(players).rename(
        columns={"Id": "PlayerId", "Player": "Player", "Team": "Team"}
    )
    manager_id_map = db.sync_managers(league_id, players_df)

    gw_data = gwk.get_gameweek_data()["events"]
    gameweeks_df = pd.DataFrame([
        {
            "FplGameweekId": gw["id"],
            "Name": f"Gameweek {gw['id']}",
            "DeadlineTime": gw["deadline_time"],
            "Finished": gw["finished"],
            "IsCurrent": gw["is_current"],
        }
        for gw in gw_data
    ])
    gameweek_id_map = db.sync_gameweeks(config.SEASON_ID, gameweeks_df)

    return league_id, manager_id_map, gameweek_id_map


def refGw(gw=None):
    """Refresh the latest ongoing/completed gameweek's data."""
    league_id, manager_id_map, gameweek_id_map = _ensure_reference_tables()
    lg = league(config.FPL_LEAGUE_ID)
    plList = lg.get_league_players()
    currGw = gwk.get_recent_completed_gameweek()

    db.delete_gameweek(currGw[0], gameweek_id_map)
    gw_plr_list = []

    for i in plList:
        plr_dict = gwk.get_gw_data(i, currGw[0])
        gw_plr_list.append(plr_dict)

    gw_df = pd.DataFrame.from_records(gw_plr_list)
    gw_df['Rank'] = gw_df.groupby('Gameweek')['Points'].rank(ascending=False, method='dense')

    db.upsert_gameweek(gw_df, manager_id_map, gameweek_id_map, config.SEASON_ID)
    refMnth(currGw[0], manager_id_map, gameweek_id_map)
    refOverall(manager_id_map)
    db.log_data_refresh(
        gameweek_id=gameweek_id_map.get(currGw[0]),
        status="success",
        notes="refGw completed",
    )


def refMnth(g, manager_id_map=None, gameweek_id_map=None):
    """Refresh monthly results for all months up to the ongoing one."""
    if manager_id_map is None or gameweek_id_map is None:
        _, manager_id_map, gameweek_id_map = _ensure_reference_tables()

    phases = gwk.get_phases()
    gw_mnth_lkp = pd.DataFrame(columns=['Gameweek', 'Month'])
    for i in range(1, g + 1):
        for k, v in phases.items():
            if v[0] <= i <= v[1] and k != 'Overall':
                df_temp = pd.DataFrame([{'Gameweek': i, 'Month': k}])
                gw_mnth_lkp = pd.concat([gw_mnth_lkp, df_temp], ignore_index=True).sort_values(by=['Gameweek'])

    latest_gw = db.load_gameweek_for_refresh().astype(
        {'Gameweek': 'int64', 'Points': 'int64'}
    )
    merged_df = pd.merge(latest_gw, gw_mnth_lkp, on='Gameweek')

    merged_mth_df = merged_df.groupby(['PlayerId', 'Player', 'Month'])['Points'].sum().reset_index()
    merged_mth_df['Rank'] = merged_mth_df.groupby(['Month'])['Points'].rank(method='dense', ascending=False)

    db.upsert_monthly(merged_mth_df, manager_id_map, config.SEASON_ID)


def refOverall(manager_id_map=None):
    """Refresh overall points and rank data."""
    if manager_id_map is None:
        _, manager_id_map, _ = _ensure_reference_tables()

    lg = league(config.FPL_LEAGUE_ID)
    standings_df = lg.get_league_standings()
    db.upsert_overall(standings_df, manager_id_map, config.SEASON_ID)
```

The `if __name__ == '__main__':` block stays the same.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/test_refresh_data.py::test_refOverall_upserts_standings_to_supabase -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Utils/refreshData.py tests/test_refresh_data.py
git commit -m "refactor: write refresh data to parameterized Supabase schema"
```

---

### Task 8: Migrate View Reads

**Files:**
- Modify: `views/about_me.py:1-5`, `views/about_me.py:41-68`
- Modify: `views/analytics.py:1-12`, `views/analytics.py:21-25`
- Modify: `views/minileague.py:1-11` (remove unused import)

**Interfaces:**
- Consumes: `supabase_conn.load_data_date()`, `supabase_conn.load_gameweek()`.
- Produces: Views render unchanged; `views/minileague.py` drops the stale `gs` import.

- [ ] **Step 1: Update `views/about_me.py`**

Change the imports at the top:

```python
from datetime import datetime, timedelta
import Utils.refreshData as rd
import streamlit as st
from Utils.league import *
import Utils.supabase_conn as db
```

Change the refresh-timestamp read:

```python
dataDate = db.load_data_date()
```

The rest of the file stays the same because `load_data_date()` already returns a one-row DataFrame with a `DataAsOf` string formatted `'%m/%d/%Y %H:%M:%S'`.

- [ ] **Step 2: Update `views/analytics.py`**

Change the imports:

```python
import time
import matplotlib.pyplot as plt
import streamlit as st
from Utils.league import *
import plyr_history as ph
import pandas as pd
from streamlit import session_state as session_state
import Utils.supabase_conn as db
import altair as alt
```

Change the gameweek load:

```python
# Get gameweek data from Supabase
gw_data = db.load_gameweek()[['Player', 'Points', 'Gameweek']] \
    .astype({'Points': 'int64', 'Gameweek': 'int64'})
```

- [ ] **Step 3: Clean up `views/minileague.py`**

Remove the unused `gs` import. The top of the file becomes:

```python
import pandas as pd
import streamlit as st
import Utils.gameweek as gwk
from Utils.league import *
import Utils.standings as stg
import urllib.parse
```

- [ ] **Step 4: Run a smoke test that views import without error**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
python -c "import views.about_me; import views.analytics; import views.minileague; print('views import OK')"
```

Expected: prints `views import OK`.

- [ ] **Step 5: Commit**

```bash
git add views/about_me.py views/analytics.py views/minileague.py
git commit -m "refactor: switch view reads to Supabase and drop stale gsheet imports"
```

---

### Task 9: Create Google Sheets to Supabase Migration Script

**Files:**
- Create: `scripts/migrate_from_gsheets.py`
- Test: Run the script once against a new Supabase project and verify row counts.

**Interfaces:**
- Consumes: `Utils.gsheet_conn.data_load()`, `Utils.league.league`, `Utils.gameweek.get_gameweek_data()`, `Utils.supabase_conn.sync_*` and `upsert_*`, `Utils.config.*`.
- Produces: All historical rows copied from Google Sheets into Supabase with reference tables populated for the configured season/league.

- [ ] **Step 1: Write the migration script**

Create `scripts/migrate_from_gsheets.py`:

```python
"""
One-time migration from Google Sheets to Supabase.
Run this locally after creating the Supabase project and running schema.sql.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import Utils.gsheet_conn as gs
import Utils.supabase_conn as db
from Utils.league import league
import Utils.gameweek as gwk
from Utils import config


def main():
    lg = league(config.FPL_LEAGUE_ID)
    league_id = db.sync_league(config.SEASON_ID, config.FPL_LEAGUE_ID, lg.get_league_name())

    # Sync managers from the FPL API.
    players = lg.get_league_players()
    players_df = pd.DataFrame.from_records(players).rename(
        columns={"Id": "PlayerId", "Player": "Player", "Team": "Team"}
    )
    manager_id_map = db.sync_managers(league_id, players_df)

    # Sync gameweeks from the FPL API bootstrap-static.
    gw_events = gwk.get_gameweek_data()["events"]
    gameweeks_df = pd.DataFrame([
        {
            "FplGameweekId": gw["id"],
            "Name": f"Gameweek {gw['id']}",
            "DeadlineTime": gw["deadline_time"],
            "Finished": gw["finished"],
            "IsCurrent": gw["is_current"],
        }
        for gw in gw_events
    ])
    gameweek_id_map = db.sync_gameweeks(config.SEASON_ID, gameweeks_df)

    # Overall sheet does not include PlayerId, so map from the league API by name.
    print("Loading Overall sheet...")
    ovr = gs.data_load('Overall', ['Rank', 'Player', 'Points', 'Last_Rank']).astype(
        {'Rank': 'int64', 'Last_Rank': 'int64', 'Points': 'int64'}
    )
    name_to_id = {name: fpl_id for fpl_id, name in players_df.set_index('PlayerId')['Player'].to_dict().items()}
    ovr['PlayerId'] = ovr['Player'].map(name_to_id)
    missing = ovr[ovr['PlayerId'].isna()]
    if not missing.empty:
        print("Warning: could not map player IDs for:", missing['Player'].tolist())
    db.upsert_overall(ovr, manager_id_map, config.SEASON_ID)
    print(f"Upserted {len(ovr)} overall rows.")

    # Gameweek sheet includes PlayerId.
    print("Loading Gameweek sheet...")
    gw = gs.data_load('Gameweek', ['PlayerId', 'Player', 'Gross', 'Transfer', 'Points', 'Rank', 'Gameweek']).astype(
        {'PlayerId': 'int64', 'Gameweek': 'int64', 'Points': 'int64', 'Gross': 'int64', 'Transfer': 'int64', 'Rank': 'int64'}
    )
    db.upsert_gameweek(gw, manager_id_map, gameweek_id_map, config.SEASON_ID)
    print(f"Upserted {len(gw)} gameweek rows.")

    # Monthly sheet includes PlayerId.
    print("Loading Monthly sheet...")
    mn = gs.data_load('Monthly', ['PlayerId', 'Player', 'Points', 'Rank', 'Month']).astype(
        {'PlayerId': 'int64', 'Points': 'int64', 'Rank': 'int64'}
    )
    db.upsert_monthly(mn, manager_id_map, config.SEASON_ID)
    print(f"Upserted {len(mn)} monthly rows.")

    # Refresh timestamp.
    print("Loading DataDate sheet...")
    data_date = gs.data_load('DataDate', ['DataAsOf'])
    if not data_date.empty:
        raw = str(data_date.loc[0, 'DataAsOf']).strip()
        for fmt in ('%m/%d/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                refreshed_at = pd.to_datetime(raw, format=fmt)
                break
            except ValueError:
                continue
        else:
            refreshed_at = pd.to_datetime(raw)

        current_gw = gwk.get_recent_completed_gameweek()
        gw_id = gameweek_id_map.get(current_gw[0]) if current_gw else None
        db.log_data_refresh(
            gameweek_id=gw_id,
            status="migrated",
            notes=f"Migrated from Google Sheets on {refreshed_at.isoformat()}",
        )
        print(f"Logged migration refresh: {refreshed_at}")

    print("Migration complete.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run the script against the new Supabase project**

Ensure `.streamlit/secrets.toml` has both Google Sheets and Supabase credentials populated, then run:

```bash
cd "/Users/himanshu/Pet Projects/FPL"
source venv/bin/activate
python scripts/migrate_from_gsheets.py
```

Expected: script prints row counts for overall, gameweek and monthly rows, and no errors.

- [ ] **Step 3: Verify row counts and referential integrity in Supabase**

In the Supabase Table Editor, check that:
- `league` has one row with `fpl_league_id = configured FPL_LEAGUE_ID` and `season_id = configured SEASON_ID`.
- `managers` has one row per league player.
- `gameweek` has 38 rows for the season.
- `overall_standings` has one row per manager.
- `gameweek_results` has `(managers × gameweeks)` rows.
- `monthly_results` has `(managers × completed months)` rows.
- `data_refresh_log` has at least the migrated row.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_from_gsheets.py
git commit -m "feat: add parameterized one-time migration script from Google Sheets to Supabase"
```

---

### Task 10: Add Unit Tests for the Data Layer

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_supabase_conn.py` (extend from Task 5)
- Modify: `tests/test_standings.py` (extend from Task 6)
- Modify: `tests/test_refresh_data.py` (extend from Task 7)
- Test: `pytest tests/ -v`

**Interfaces:**
- Consumes: `Utils.supabase_conn` helpers, `Utils.standings`, `Utils.refreshData`.
- Produces: A passing test suite covering reference sync, read shapes, winnings calculation, and refresh write path.

- [ ] **Step 1: Create shared fixtures**

Create `tests/conftest.py`:

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def sample_overall():
    return pd.DataFrame({
        "Rank": [1, 2],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Last_Rank": [2, 1],
    })


@pytest.fixture
def sample_gameweek():
    return pd.DataFrame({
        "Player": ["A B", "C D", "A B"],
        "Gross": [50, 45, 55],
        "Transfer": [4, 0, 2],
        "Points": [46, 45, 53],
        "Rank": [1, 2, 1],
        "Gameweek": [1, 1, 2],
    })


@pytest.fixture
def sample_monthly():
    return pd.DataFrame({
        "Player": ["A B", "C D"],
        "Points": [99, 45],
        "Rank": [1, 2],
        "Month": ["August", "August"],
    })
```

- [ ] **Step 2: Extend `tests/test_supabase_conn.py`**

Add tests for manager and gameweek sync and read helpers:

```python
def test_sync_managers_returns_mapping(monkeypatch):
    client = _make_mock_client()
    client._selects["managers"] = [
        {"id": 1, "fpl_entry_id": 777321, "league_id": 282978, "player_name": "A B", "team_name": "T1"},
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    managers_df = pd.DataFrame({
        "PlayerId": [777321],
        "Player": ["A B"],
        "Team": ["T1"],
    })
    mapping = supabase_conn.sync_managers(282978, managers_df)

    assert mapping == {777321: 1}
    assert len(client._upserts) == 1


def test_sync_gameweeks_returns_mapping(monkeypatch):
    client = _make_mock_client()
    client._selects["gameweek"] = [
        {"id": 101, "fpl_gameweek_id": 1, "season_id": "2025-26", "name": "Gameweek 1", "finished": True, "is_current": False},
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: client)

    gameweeks_df = pd.DataFrame({
        "FplGameweekId": [1],
        "Name": ["Gameweek 1"],
        "DeadlineTime": ["2025-08-15T17:30:00Z"],
        "Finished": [True],
        "IsCurrent": [False],
    })
    mapping = supabase_conn.sync_gameweeks("2025-26", gameweeks_df)

    assert mapping == {1: 101}


def test_load_overall_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {"manager_id": 1, "player_name": "Himanshu Masani", "rank": 1, "points": 1950, "last_rank": 2}
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: _mock_select_client(overall_rows=rows))

    df = supabase_conn.load_overall()
    assert list(df.columns) == ["Rank", "Player", "Points", "Last_Rank"]
    assert df["Rank"].dtype == "int64"
    assert df["Points"].dtype == "int64"
    assert df["Last_Rank"].dtype == "int64"
    assert df.loc[0, "Player"] == "Himanshu Masani"


def test_load_gameweek_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {
            "manager_id": 1,
            "gameweek_id": 101,
            "player_name": "A B",
            "gross": 50,
            "transfer": 4,
            "points": 46,
            "rank": 1,
        }
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: _mock_select_client(gameweek_rows=rows))

    df = supabase_conn.load_gameweek()
    assert list(df.columns) == ["Player", "Gross", "Transfer", "Points", "Rank", "Gameweek"]
    for col in ["Gross", "Transfer", "Points", "Rank", "Gameweek"]:
        assert df[col].dtype == "int64"


def test_load_gameweek_for_refresh_returns_player_id(monkeypatch):
    gameweek_rows = [
        {"manager_id": 1, "gameweek_id": 101, "player_name": "A B", "points": 46, "rank": 1}
    ]
    manager_rows = [
        {"id": 1, "fpl_entry_id": 777321, "league_id": 282978, "player_name": "A B", "team_name": "T1"}
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: _mock_select_client(
        gameweek_rows=gameweek_rows,
        manager_rows=manager_rows,
    ))

    df = supabase_conn.load_gameweek_for_refresh()
    assert list(df.columns) == ["PlayerId", "Player", "Points", "Gameweek"]
    assert df["PlayerId"].dtype == "int64"


def test_load_monthly_returns_expected_columns_and_types(monkeypatch):
    rows = [
        {"manager_id": 1, "player_name": "A B", "points": 99, "rank": 1, "month": "August"}
    ]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: _mock_select_client(monthly_rows=rows))

    df = supabase_conn.load_monthly()
    assert list(df.columns) == ["Player", "Points", "Rank", "Month"]
    assert df["Points"].dtype == "int64"
    assert df["Rank"].dtype == "int64"


def test_load_data_date_returns_formatted_string(monkeypatch):
    rows = [{"refreshed_at": "2025-08-15T18:30:00+00:00"}]
    monkeypatch.setattr(supabase_conn, "get_client", lambda: _mock_select_client(refresh_rows=rows))

    df = supabase_conn.load_data_date()
    assert list(df.columns) == ["DataAsOf"]
    assert df.loc[0, "DataAsOf"] == "08/15/2025 18:30:00"
```

You will need to extend the helper factory to handle `manager_rows`. Add `_mock_select_client`:

```python
def _mock_select_client(overall_rows=None, gameweek_rows=None, monthly_rows=None, refresh_rows=None, manager_rows=None):
    """Return a mock client that only supports .table(name).select('*').execute()."""
    client = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        data = []
        if name == "overall_standings":
            data = overall_rows or []
        elif name == "gameweek_results":
            data = gameweek_rows or []
        elif name == "monthly_results":
            data = monthly_rows or []
        elif name == "data_refresh_log":
            order_chain = MagicMock()
            limit_chain = MagicMock()
            limit_chain.execute.return_value = FakeResponse(refresh_rows or [])
            order_chain.limit.return_value = limit_chain
            chain.select.return_value.order.return_value = order_chain
            return chain
        elif name == "managers":
            data = manager_rows or []

        chain.select.return_value.execute.return_value = FakeResponse(data)
        return chain

    client.table.side_effect = table_side_effect
    return client
```

- [ ] **Step 3: Extend `tests/test_standings.py`**

Add a test for `winnings_data` using the fixtures:

```python
from conftest import sample_gameweek, sample_monthly


def test_winnings_data_filters_and_splits_correctly(sample_gameweek, sample_monthly, monkeypatch):
    monkeypatch.setitem(st.st.session_state, "gw_id", 2)
    monkeypatch.setitem(st.st.session_state, "gw_status", True)
    monkeypatch.setitem(st.st.session_state, "completed_months", ["August"])

    gw_win, mn_win = stg.winnings_data(sample_gameweek, sample_monthly)

    # Both gameweeks completed, so both rows should appear.
    assert len(gw_win) == len(sample_gameweek)
    assert "Total" in gw_win.columns
    # One winner per gameweek in the sample, so 300/1 = 300.
    assert gw_win.loc[gw_win["Rank"] == 1, "Total"].iloc[0] == 300.0

    # Monthly has one winner, so 530/1 = 530.
    assert len(mn_win) == len(sample_monthly)
    assert mn_win.loc[mn_win["Rank"] == 1, "Total"].iloc[0] == 530.0
```

- [ ] **Step 4: Extend `tests/test_refresh_data.py`**

Add a test for `refGw` flow:

```python
def test_refGw_deletes_then_upserts_gameweek(monkeypatch):
    pl = [{"Id": 777321, "Team": "T1", "Player": "A B"}]
    gw_data = {
        "PlayerId": 777321,
        "Player": "A B",
        "Gross": 50,
        "Transfer": 4,
        "Points": 46,
        "Rank": "",
        "Gameweek": 1,
    }
    manager_map = {777321: 1}
    gameweek_map = {1: 101}

    with patch("Utils.refreshData.lg.get_league_players", return_value=pl), \
         patch("Utils.refreshData.gwk.get_recent_completed_gameweek", return_value=[1, True]), \
         patch("Utils.refreshData.gwk.get_gw_data", return_value=gw_data), \
         patch("Utils.refreshData._ensure_reference_tables", return_value=(282978, manager_map, gameweek_map)), \
         patch("Utils.refreshData.db.delete_gameweek") as mock_delete, \
         patch("Utils.refreshData.db.upsert_gameweek") as mock_upsert, \
         patch("Utils.refreshData.refMnth") as mock_refMnth, \
         patch("Utils.refreshData.refOverall") as mock_refOverall, \
         patch("Utils.refreshData.db.log_data_refresh") as mock_log:
        rd.refGw()

    mock_delete.assert_called_once_with(1, gameweek_map)
    mock_upsert.assert_called_once()
    passed_df, passed_manager_map, passed_gameweek_map, passed_season = mock_upsert.call_args[0]
    assert passed_df.loc[0, "Gameweek"] == 1
    assert passed_manager_map == manager_map
    assert passed_gameweek_map == gameweek_map
    assert passed_season == "2025-26"
    mock_refMnth.assert_called_once_with(1, manager_map, gameweek_map)
    mock_refOverall.assert_called_once_with(manager_map)
    mock_log.assert_called_once()
```

- [ ] **Step 5: Run the full test suite**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: add unit tests for parameterized Supabase relational data layer"
```

---

### Task 11: Clean Up Google Sheets Dependencies and Document

**Files:**
- Modify: `requirements.txt` (remove Google Sheets libraries)
- Modify: `README.md`
- Do not delete `Utils/gsheet_conn.py` in Phase 1; it is still needed by the migration script.
- Test: `streamlit run fpl_streamlit_app.py` smoke test, plus `pytest tests/ -v`

**Interfaces:**
- Consumes: All previous tasks.
- Produces: A codebase where the runtime persistence layer is Supabase; docs explain setup and parameterization.

- [ ] **Step 1: Remove Google Sheets-only requirements**

Edit `requirements.txt` to remove the lines that are no longer needed at runtime:

```text
st-gsheets-connection
oauth2client==4.1.3
```

Keep `toml` because it is still used by the legacy migration script to read the example template, and by Streamlit secrets parsing.

- [ ] **Step 2: Update `README.md`**

Replace the current README with:

```markdown
# FPL Fantasy Kings App

Track the proceedings of an FPL mini-league: gameweek winners, monthly winners, overall standings and winnings.

## Phase 1 Overhaul

The app has moved its persistence layer from Google Sheets to Supabase. The data model now uses reference tables for `seasons`, `league`, `managers`, `gameweek`, while statistical tables (`overall_standings`, `gameweek_results`, `monthly_results`) store denormalized player names for display. The Streamlit UI and FPL API integration remain unchanged.

### Configuration

Season and league ids are centralized in `Utils/config.py` and can be overridden without touching code:

1. **Via `.streamlit/secrets.toml`** (recommended for production):
   ```toml
   [app]
   season_id = "2025-26"
   fpl_league_id = "282978"
   league_name = "Fantasy Kings"
   ```

2. **Via environment variables** (useful for local development or CI):
   ```bash
   export FPL_SEASON_ID="2025-26"
   export FPL_LEAGUE_ID="282978"
   export FPL_LEAGUE_NAME="Fantasy Kings"
   ```

Defaults target Fantasy Kings 2025-26 (`282978`).

### Setup

1. Create a free Supabase project at https://supabase.com.
2. Open the Supabase SQL Editor and run the contents of `schema.sql`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:
   - `[app]` section (or set env vars).
   - `[supabase] url` and `key` (service role key from Project Settings → API).
   - `[connections.gsheets]` and `[google_sheets]` credentials (only needed for the one-time migration).
4. Run the migration once:
   ```bash
   python scripts/migrate_from_gsheets.py
   ```
5. Start the app:
   ```bash
   streamlit run fpl_streamlit_app.py
   ```

### Running tests

```bash
pytest tests/ -v
```

### Data model (Phase 1)

- `seasons` — one row per FPL season.
- `league` — one row per mini-league per season.
- `managers` — one row per FPL entry per league.
- `gameweek` — one row per FPL gameweek per season.
- `overall_standings` — latest overall rank/points per manager per season.
- `gameweek_results` — per-gameweek points, gross, transfer cost and rank.
- `monthly_results` — aggregated monthly points and rank.
- `data_refresh_log` — audit log of refresh operations.
```

- [ ] **Step 3: Run the full smoke test**

```bash
cd "/Users/himanshu/Pet Projects/FPL"
source venv/bin/activate
pytest tests/ -v
streamlit run fpl_streamlit_app.py -- &
sleep 5
kill %1
```

Expected: tests pass and Streamlit starts without import errors. The `kill` may print a message about the job being terminated; that is normal.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt README.md
git commit -m "docs: remove unused gsheet deps and document parameterized Supabase setup"
```

---

## Self-Review

1. **Spec coverage:**
   - Move data capture from Google Sheets to Supabase: covered by Tasks 5, 6, 7, 8.
   - Track gameweek, monthly and overall winners: covered by schema (`gameweek_results`, `monthly_results`, `overall_standings`) and loaders.
   - Track winnings: `Utils/standings.py` winnings logic unchanged; Task 6 ensures it reads from Supabase.
   - Streamlit frontend: Task 8 updates view reads; no UI behavior change.
   - Reference tables (`seasons`, `league`, `managers`, `gameweek`): covered by schema (Task 4), sync functions (Task 5), refresh pipeline (Task 7) and migration script (Task 9).
   - Parameterized season and league ids: covered by `Utils/config.py` (Task 2) and its usage throughout `Utils/supabase_conn.py`, `Utils/refreshData.py`, `scripts/migrate_from_gsheets.py`.
   - First phase / reference for later phases: schema and config are parameterized by season; README documents Phase 1 boundaries.

2. **Placeholder scan:**
   - No "TBD", "TODO", "implement later", "add appropriate error handling", or "similar to Task N" found.
   - Every step contains exact commands, code or expected output.

3. **Type consistency:**
   - `load_overall()` returns `['Rank', 'Player', 'Points', 'Last_Rank']` matching old Google Sheets loader.
   - `load_gameweek()` returns `['Player', 'Gross', 'Transfer', 'Points', 'Rank', 'Gameweek']` matching old loader (note: `Gameweek` now carries the internal `gameweek_id` integer, which is still numeric and works for filtering/sliders).
   - `load_monthly()` returns `['Player', 'Points', 'Rank', 'Month']` matching old loader.
   - `load_data_date()` returns one-row DataFrame with column `DataAsOf` formatted `'%m/%d/%Y %H:%M:%S'`.
   - `upsert_*` functions accept DataFrames with the column names produced by the existing refresh pipeline (`PlayerId`, `Player`, `Rank`, `Points`, etc.).
   - Reference sync functions return concrete mapping types consumed by the upsert functions.
   - `Utils/config.py` exposes `SEASON_ID: str`, `FPL_LEAGUE_ID: int`, `LEAGUE_NAME: str`, `LEAGUE_RECORD_ID: int` used consistently.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-05-migrate-fpl-data-layer-to-supabase.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach would you like?**
