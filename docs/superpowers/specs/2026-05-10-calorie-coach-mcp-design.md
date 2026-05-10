# Calorie & Sport Coach — MCP Server Design

> **Status:** Draft — pending sober re-read by user before implementation.
> **Date:** 2026-05-10
> **Owner:** Ethan Smadja

---

## 1. Goal

Build a personal MCP server that lets Claude act as a weight-loss coach for the user.
The user has already lost significant weight and wants ongoing accountability without paying a human coach.

The MCP exposes tools to Claude so the user can, in plain conversation:

- Log meals (with macros) and workouts
- Log body weight
- Ask Claude for analysis, daily summaries, course corrections

The MCP is a **pure journal**: it stores events and returns history. **All coaching intelligence lives in Claude's context** (system prompt / project instructions hold the user's profile, daily kcal target, goals). The MCP performs no TDEE calculation, no "kcal remaining today" logic, no goal enforcement.

**Out of scope (v1):** body measurements (waist, etc.).
**Deferred:** sleep, energy, mood — useful later but the user is "not there yet".

---

## 2. What gets tracked (v1)

| Domain                     | Logged | Notes                                                      |
|----------------------------|--------|------------------------------------------------------------|
| Meals                      | yes    | description + kcal + macros (P/C/F) + estimated/exact flag |
| Workouts                   | yes    | type, duration, kcal burned + estimated/exact flag         |
| Weight                     | yes    | scalar in kg, timestamped                                  |
| Sleep / energy / mood      | no     | deferred                                                   |
| Measurements (waist, etc.) | no     | out of scope                                               |

---

## 3. Architecture

- **Language / runtime:** Python 3.13.
- **Framework:** FastMCP (`fastmcp>=3.2.4`).
- **Transport:** HTTP (remote MCP) — server is deployed, Claude connects over the network.
- **Auth:** static bearer token in `Authorization: Bearer <token>` header (single user, sufficient).
- **DB:** Neon Postgres, accessed via the pooled endpoint (`-pooler` host) for safer connection handling and to leave the door open for serverless retargeting later.
- **Local dev:** `.env` with `DATABASE_URL` and `MCP_BEARER_TOKEN`; `fastmcp dev` for iteration.
- **Deployment target:** Railway (decided 2026-05-10). FastMCP runs as a long-running HTTP server on Railway. Connection string + bearer token via Railway env vars.
- **Timezone:** all timestamps stored in `timestamptz` (UTC). Server-side "today / yesterday / this week" use `Europe/Paris`. Claude can override with an explicit date string.

### DB layer

- **ORM:** SQLModel (built on SQLAlchemy + Pydantic). Chosen for synergy with FastMCP: one model class can serve as the DB table, the tool payload schema, and the response shape.
- **Driver:** `psycopg` (v3) or `asyncpg` under SQLModel — pick whichever SQLModel recommends for Neon's pooled endpoint at implementation time.
- **Migrations:** none for v1. DDL is applied once via a small `init_db.sql` script (the 3 `CREATE TABLE` statements). If the schema needs to evolve, we'll add Alembic later.

---

## 4. Database schema

```sql
create table meals (
  id           bigserial primary key,
  eaten_at     timestamptz not null,
  description  text not null,
  kcal         numeric(7,1) not null,
  protein_g    numeric(6,1),
  carbs_g      numeric(6,1),
  fat_g        numeric(6,1),
  source       text not null check (source in ('estimated','exact')),
  created_at   timestamptz not null default now()
);

create table workouts (
  id           bigserial primary key,
  done_at      timestamptz not null,
  type         text not null,
  duration_min integer not null,
  kcal_burned  numeric(7,1) not null,
  source       text not null check (source in ('estimated','exact')),
  notes        text,
  created_at   timestamptz not null default now()
);

create table weights (
  id           bigserial primary key,
  measured_at  timestamptz not null,
  kg           numeric(5,2) not null,
  created_at   timestamptz not null default now()
);
```

Design notes:

- `numeric` over `float` to avoid floating-point drift on kcal/macros.
- Event time (`*_at`) is separate from `created_at`, so the user can backfill ("I had lunch at noon" logged at 22:00).
- No `user_id` — single user.
- `delete` is a hard delete; no soft-delete column. Acceptable for personal use.
- No indexes initially; volume is tiny (tens of rows/day at most).

---

## 5. MCP tools exposed to Claude

To keep Claude's tool catalog small (every tool description costs context), tools are grouped **by entity, not by action**. Each entity tool takes a discriminated `op` union (modeled with Pydantic; FastMCP derives the JSON schema). All write/update ops return the affected row including its `id` so Claude can reference it later.

### 5 tools total

1. **`meals(op)`** — `op ∈ { log, update, delete, list }`
   - `log`: `description, kcal, source, eaten_at?, protein_g?, carbs_g?, fat_g?`
   - `update`: `id, fields...` (partial)
   - `delete`: `id`
   - `list`: `from?, to?` → rows with IDs

2. **`workouts(op)`** — `op ∈ { log, update, delete, list }`
   - `log`: `type, duration_min, kcal_burned, source, done_at?, notes?`
   - `update`: `id, fields...`
   - `delete`: `id`
   - `list`: `from?, to?`

3. **`weights(op)`** — `op ∈ { log, update, delete, list }`
   - `log`: `kg, measured_at?`
   - `update`: `id, fields...`
   - `delete`: `id`
   - `list`: `from?, to?`

4. **`get_summary(date?)`** — daily aggregates for `date` (default = today, `Europe/Paris`): total kcal in, total kcal burned, net kcal, macro totals, latest weight of the day if any. No targets, no "remaining". Optionally surfaces estimated/exact ratio.

5. **`get_history(days)`** — array of daily aggregates over the last `N` days, same shape as `get_summary` per day, for trend analysis.

### Conventions

- `*_at` parameters default to "now" (UTC) when omitted.
- Date parameters are ISO-8601 strings; bare dates (`YYYY-MM-DD`) are interpreted as `Europe/Paris` local days.
- Pydantic discriminated unions on `op` give Claude per-operation guidance in the schema while keeping the tool surface compact.
- Caveat: confirm at implementation time that FastMCP 3.2.4 cleanly serializes discriminated unions into the MCP tool schema. If not, fall back to per-operation tools for the affected entity.

---

## 6. Resolved decisions

- Profile / goals live in Claude's context, **not** in the DB.
- Calorie source flag: `estimated | exact` — stored, Claude decides which mode to use per meal.
- Edits and deletes are first-class v1 features.
- Timezone is fixed to `Europe/Paris` server-side.
- Auth: static bearer token.
- Deployment: Railway (long-running HTTP server).
- DB: Neon (pooled endpoint), accessed via SQLModel.
- Tool surface: 5 entity-grouped tools with Pydantic discriminated unions.

---

## 7. Open / deferred items

- [ ] Pick DB driver (`psycopg` vs `asyncpg`) at implementation time.
- [ ] Sleep / energy / mood — future iteration once the v1 habit sticks.
- [x] `get_summary` and `get_history` surface the estimated/exact ratio so Claude can flag "today's data is mostly estimated, take with a grain of salt".

---

## 8. Decisions log

- 2026-05-10: Goal = weight loss coaching (single user, self).
- 2026-05-10: Scope = meals + macros + workouts + weight. Sleep/energy/mood deferred. Measurements out.
- 2026-05-10: Storage = Neon Postgres.
- 2026-05-10: Profile lives in Claude's context, not in DB. MCP is a pure journal.
- 2026-05-10: Calorie estimation = hybrid (estimated/exact flag stored).
- 2026-05-10: Edits/deletes included in v1.
- 2026-05-10: Timezone = `Europe/Paris`, UTC in DB.
- 2026-05-10: Auth = static bearer token.
- 2026-05-10: DB schema validated (3 tables).
- 2026-05-10: ORM = SQLModel (synergy with FastMCP via shared Pydantic models). Driver picked at implementation time.
- 2026-05-10: Tool surface = 5 tools grouped by entity (`meals`, `workouts`, `weights`, `get_summary`, `get_history`) using Pydantic discriminated unions on `op`, instead of 13 per-action tools.
- 2026-05-10: Deployment target = Railway.
- 2026-05-10: `get_summary` / `get_history` surface estimated/exact ratio.
