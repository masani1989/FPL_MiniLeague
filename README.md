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

## Phase 2: Automated Refresh and Winnings Persistence

### What changed

- A GitHub Actions workflow (`.github/workflows/refresh-supabase.yml`) refreshes
  Supabase from the FPL API every hour.
- Gameweek, monthly and overall winnings are now stored in Supabase:
  `gw_winnings`, `monthly_winnings`, `overall_prizes`, `winnings_summary`.
- The Streamlit app reads the pre-computed `winnings_summary` instead of
  recalculating on every page load.

### Database migration for existing deployments

If you already ran Phase 1 `schema.sql`, run this migration once to add the
winnings tables:

```bash
psql $SUPABASE_DB_URL -f migrations/002_phase2_winnings_and_workflow.sql
```

### GitHub Actions secrets

In the GitHub repository settings, add these secrets:

- `SUPABASE_URL` — project URL, e.g. `https://<ref>.supabase.co`
- `SUPABASE_KEY` — **service role key** (required for upserts/deletes)
- `FPL_SEASON_ID` — e.g. `2026-27`
- `FPL_LEAGUE_ID` — e.g. `581588`
- `FPL_LEAGUE_NAME` — e.g. `Fantasy Kings`

### Manual trigger / testing the workflow locally

You can run the same command the workflow uses from a shell with the env vars set:

```bash
export FPL_SEASON_ID="2026-27"
export FPL_LEAGUE_ID="581588"
export FPL_LEAGUE_NAME="Fantasy Kings"
export SUPABASE_URL="https://<ref>.supabase.co"
export SUPABASE_KEY="<service-role-key>"

python Utils/refreshData.py --all
```

### Data refresh semantics

| Table | Strategy | Notes |
|-------|----------|-------|
| `seasons` | seed / upsert | Inserted by `schema.sql`. |
| `league` | upsert | One row per FPL league per season. |
| `managers` | upsert | Names/teams update if changed. |
| `gameweek` | upsert | Marks finished/current flags. |
| `overall_standings` | upsert | Replaced per manager per season. |
| `gameweek_results` | delete + insert current GW | Current GW is fully replaced each run. |
| `monthly_results` | upsert | Recomputed for every completed month up to latest GW. |
| `data_refresh_log` | append | One audit row per run. |
| `gw_winnings` | upsert | Recomputed for every finished gameweek. |
| `monthly_winnings` | upsert | Recomputed for every completed month. |
| `overall_prizes` | upsert | Written only after GW 38 is finished. |
| `winnings_summary` | upsert | One summary row per manager per season. |

## Phase 3: FastAPI + Ollama Backend and Telegram Bot

### What changed

- New `backend/` package with a FastAPI app, async Supabase client, async FPL client,
  Ollama agent, and Telegram bot.
- AI tools available via chat:
  - `get_manager_profile`, `get_standings`, `get_winnings_info`, `compare_managers`
  - `recommend_transfer`, `recommend_captain`, `evaluate_team`, `project_finish_probability`
- Telegram bot supports both commands and natural language.
- Scheduled announcements: upcoming deadline, gameweek results, monthly results,
  pre-gameweek captain/transfer suggestions.
- Group chat behaviour: bot only replies when mentioned or replied to.
- Private chat behaviour: every message is processed; managers can link their FPL
  entry with `/register <fpl_entry_id>` for personalised responses.

### Setup

1. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Pull the Ollama model locally:
   ```bash
   ollama pull llama3.1
   ```

3. Create a Telegram bot with [@BotFather](https://t.me/botfather) and copy the token.

4. Set environment variables:
   ```bash
   export OLLAMA_BASE_URL="http://localhost:11434"
   export OLLAMA_MODEL="llama3.1"
   export SUPABASE_URL="https://<ref>.supabase.co"
   export SUPABASE_KEY="<service-role-key>"
   export TELEGRAM_BOT_TOKEN="<your-bot-token>"
   export TELEGRAM_WEBHOOK_URL=""   # leave empty for local polling, set for production
   export SEASON_ID="2026-27"
   export FPL_LEAGUE_ID="581588"
   ```

5. Run the migration for Telegram tables:
   ```bash
   psql $SUPABASE_DB_URL -f migrations/003_phase3_telegram_and_backend.sql
   ```

6. Start the backend:
   ```bash
   python scripts/run_backend.py
   ```

### Testing the backend

```bash
pytest tests/backend -v
```

### Telegram webhook (production)

Set `TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook`. The bot
will register the webhook on startup and FastAPI will receive updates at that
path. For local development, leave `TELEGRAM_WEBHOOK_URL` empty and the bot will
use long-polling.

### Group vs private chat design

- **Group:** Add the bot as a normal member. Mention `@botname` or reply to the
  bot's messages. Good for league-wide announcements and quick public queries.
- **Private:** Start a direct chat with the bot. Run `/register <fpl_entry_id>`
  so commands like `/profile`, `/transfers`, and `/captain` default to your team.
  Private chats also receive all scheduled announcements if registered.
