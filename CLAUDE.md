# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## End-of-session check

Run `make check` at the end of every coding session. It runs ruff + ty and is the gate before any commit.

## Commands

All workflow tasks are driven from the `Makefile`. Run `make help` to list every target with descriptions.

Day-to-day:
- `make dev` — run the MCP server locally at http://localhost:8000 (reads `.env`)
- `make check` — `ruff check .` + `uvx ty check`
- `make fix` — `ruff check --fix` + `ruff format`
- `make logs` — tail Railway logs for the `coach-mcp` service
- `make pull-env` — overwrite `.env` from Railway variables

Bootstrap / deploy (idempotent):
- `make init` — chains `check-cli → provision → domain → push-env → deploy`
- `make deploy` — `railway up --service coach-mcp --detach`

There are **no tests** in this repo. Don't add a test command to the Makefile unless tests are introduced.

## Architecture

### Single-tenant MCP server, OAuth-gated

`main.py` → `coach.config.load_settings()` → `coach.server.build_server()` → `mcp.run(transport="http")`.

Authentication is **not** a bearer token — it's GitHub OAuth via FastMCP's `OAuthProxy`. Clients (claude.ai, Cursor) discover the flow at `/.well-known/oauth-authorization-server`, get redirected to GitHub, and the server only accepts tokens whose GitHub login matches `ALLOWED_GITHUB_LOGIN`. The allowlist is enforced by subclassing `GitHubTokenVerifier` (see `AllowlistedGitHubVerifier` in `coach/server.py`). Required env vars at boot: `DATABASE_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `BASE_URL`, `ALLOWED_GITHUB_LOGIN`.

A public `/health` endpoint is registered via `@mcp.custom_route` — it's the Railway healthcheck target and is the only unauthenticated route besides the OAuth metadata endpoints.

### Tools follow a discriminated-union payload pattern

The MCP exposes only 5 tools (`meals`, `workouts`, `weights`, `get_summary`, `get_history`), but `meals`/`workouts`/`weights` each multiplex 4 operations (`log` / `update` / `delete` / `list`) through a single `payload: dict` argument. The dispatch logic:

1. `coach/ops/payloads.py` defines Pydantic models per op (e.g. `LogMeal`, `UpdateMeal`, `DeleteMeal`, `ListMeals`) plus a discriminated union (`MealsPayload`) tagged by the `op` field.
2. `coach/ops/<entity>.py` validates the raw dict via a module-level `TypeAdapter`, then `isinstance`-dispatches to `_log` / `_update` / `_delete` / `_list`.
3. All four handlers share a `Session` injected by the tool wrapper in `coach/server.py`.

When adding a new operation to an existing tool, add the payload class + extend the union in `payloads.py`, add an `isinstance` branch in the handler, and update the tool's `description` string in `server.py` (clients rely on it for argument shape).

### Postgres schema is auto-created at boot

`coach/db.py:make_engine()` calls `SQLModel.metadata.create_all(engine)` on every server start. No migration tool, no `init_db.sql` run step. Tables are defined in `coach/models.py` (`Meal`, `Workout`, `Weight`). If you add a new table, just declare the SQLModel class — it'll be created next boot. Schema **changes** to existing tables (renames, drops) are *not* handled and need manual SQL.

### Time handling is Europe/Paris

`coach/time.py` is the single source for "what's today". `paris_day_bounds()` returns `[start, end)` in UTC for a Paris-local date; `parse_iso_or_date()` accepts either `YYYY-MM-DD` or full ISO datetimes. The DB stores everything in `timestamptz` UTC; conversion happens at the boundary. `get_summary` defaults to "today in Paris" when no date is passed.

### SQLModel + `col()` for type-checker compatibility

`ty` (and to some extent pyright) can't infer that `Meal.eaten_at` returns an `InstrumentedAttribute` (not a `datetime`) at class-access. **All `order_by`/`.desc()` calls must wrap the column in `sqlmodel.col(...)`**. Pattern: `select(Meal).order_by(col(Meal.eaten_at))`. The `where()` clauses are fine without it.

### Config-as-code

`railway.toml` overrides the Railway dashboard. The healthcheck path (`/health`), start command (`uv run python main.py`), and restart policy live there — change them via the file, not the dashboard.

## Important file references

- `coach/server.py` — tool wiring, OAuth setup, allowlist enforcement
- `coach/ops/payloads.py` — discriminated union schemas (add new ops here first)
- `coach/db.py` — engine creation, URL scheme rewriting (`postgres://` → `postgresql+psycopg://`)
- `coach/time.py` — all date/time logic, Paris timezone
- `railway.toml` — build/deploy config
