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
   fpl_league_id = "581588"
   league_name = "Fantasy Kings"
   ```

2. **Via environment variables** (useful for local development or CI):
   ```bash
   export FPL_SEASON_ID="2025-26"
   export FPL_LEAGUE_ID="581588"
   export FPL_LEAGUE_NAME="Fantasy Kings"
   ```

Defaults target Fantasy Kings 2025-26 (`581588`).

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

2. Create a Telegram bot with [@BotFather](https://t.me/botfather) and copy the token.

3. Set environment variables (or add them to `.streamlit/secrets.toml` under `[backend]`):
   ```bash
   export OLLAMA_BASE_URL="http://localhost:11434"
   export OLLAMA_MODEL="llama3.2"
   export OLLAMA_API_KEY="<your-ollama-api-key>"   # only for Ollama Cloud; local ignores this
   export OPENAI_API_KEY="<your-api-key>"          # optional: for OpenAI-compatible providers
   export SUPABASE_URL="https://<ref>.supabase.co"
   export SUPABASE_KEY="<service-role-key>"
   export TELEGRAM_BOT_TOKEN="<your-bot-token>"
   export TELEGRAM_WEBHOOK_URL=""   # leave empty for local polling, set for production
   export TELEGRAM_WEBHOOK_SECRET=""  # set when using a webhook so Telegram can authenticate callbacks
   export SEASON_ID="2026-27"
   export FPL_LEAGUE_ID="581588"
   ```

   - Local Ollama: `OLLAMA_BASE_URL=http://localhost:11434`, no API key needed.
   - Ollama Cloud: `OLLAMA_BASE_URL=https://ollama.com`, set `OLLAMA_API_KEY`.
   - OpenAI-compatible provider: set `OLLAMA_BASE_URL` to their `/v1` endpoint and `OPENAI_API_KEY`.

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

## Phase 4: Host Backend on Render + Telegram Webhooks

### 1. Create the Render service

- Push `major_update` to GitHub.
- In Render dashboard: **New > Web Service**.
- Connect the GitHub repo and select branch `major_update`.
- Render will read `render.yaml` (Blueprint) and set:
  - Build command: `pip install -r requirements.txt`
  - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
  - Free plan.

### 2. Create environment group

In Render, create an **Environment Group** named `fpl-backend-secrets` and add:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OLLAMA_BASE_URL` (e.g., `https://ollama.com` for Ollama Cloud)
- `OLLAMA_MODEL` (e.g., `glm-5.2:cloud`)
- `OLLAMA_API_KEY`
- `OPENAI_API_KEY` (optional fallback)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_URL` = `https://<your-render-service>.onrender.com/telegram/webhook`
- `TELEGRAM_WEBHOOK_SECRET` — optional but recommended; must match the secret configured with BotFather via `setWebhook`
- `FPL_LEAGUE_ID`
- `SEASON_ID`

Attach the group to the web service.

### 3. Configure Telegram bot with BotFather

- Create bot via [@BotFather](https://t.me/BotFather), get token.
- Set `/setprivacy` to **Disabled** so the bot can read group messages.
- Add bot to your FPL mini-league group.

### 4. Verify deployment

- Visit `https://<your-service>.onrender.com/health`.
- Send `/start` to the bot in a private chat; it should reply.
- Mention the bot in the group; it should reply.

### Restricting announcements to one group

Set `ALLOWED_TELEGRAM_CHAT_IDS` (env var or `[backend] allowed_telegram_chat_ids` in secrets.toml) to a comma-separated list of chat IDs that may receive scheduled announcements. Group chats have negative IDs.

To find your group's chat ID:

1. Add the bot to the group.
2. Send a message in the group.
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and look for `"chat":{"id":-123456789,...}`.

Leave empty to allow all chats (default).

### Keep-alive (GitHub Actions)

Render's free tier has no cron jobs, so keep-alive runs as a GitHub Actions scheduled workflow. `.github/workflows/keepalive.yml` pings the backend's `/health` endpoint every 10 minutes so the free-tier web service does not sleep.

- The default health URL is `https://fpl-backend-v4fu.onrender.com/health`. To override it, set a repository variable `BACKEND_HEALTH_URL` (Settings → Secrets and variables → Actions → Variables).
- **Scheduled workflows only run on the default branch (`main`).** Until `keepalive.yml` is merged to `main`, the schedule is dormant — test it with a manual `workflow_dispatch` run from the Actions tab.
- GitHub Actions is free and unlimited for public repos.

### Notes

- Render free tier sleeps after 15 minutes of inactivity. First request after sleep will be slow (~30–60s).
- Local Ollama does not work on Render; use Ollama Cloud or an OpenAI-compatible provider.
- Telegram webhook is set automatically on startup if `TELEGRAM_WEBHOOK_URL` is set.

## Last Man Standing

A pilot knockout contest running alongside the main league with the same
managers. **There is no cash prize** — it is a friendly side contest.

### Rules

- Each finished gameweek, the alive manager with the lowest **First XI** score
  is eliminated (one per gameweek).
- **Chips ignored**, captain capped at **x2**, bench excluded.
- The contest continues until one survivor remains.

### Tiebreakers

When two or more alive managers share the lowest First XI score, the
elimination is decided by, in order:

1. Goals scored
2. Goals conceded
3. Clean sheets
4. Assists
5. Bench points
6. Coin toss (deterministic seeded toss, only on a full 6-stat tie)

### How it runs

- The refresh pipeline (`python Utils/refreshData.py --all`) processes the
  latest finished gameweek as part of the normal refresh.
- A scheduled Telegram announcement posts each elimination once (deduped on
  retry).
- Backfill from a given gameweek:

  ```bash
  python -m last_man_standing.runner --backfill --from-gw 1
  ```

  `--to-gw N` caps the range (default: latest finished gameweek).

### Telegram

- `/lms` — current survivor standings.
- `/lms <gameweek>` — that gameweek's scorecard (eliminated manager + tiebreakers).

### Streamlit

A "Last Man Standing" page shows survivors and per-gameweek scorecards.
