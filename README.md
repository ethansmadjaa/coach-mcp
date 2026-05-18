# Coach MCP

[![Python](https://img.shields.io/badge/python-3.13+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.2+-FF6F00.svg)](https://gofastmcp.com)
[![SQLModel](https://img.shields.io/badge/SQLModel-0.0.22+-009688.svg)](https://sqlmodel.tiangolo.com)
[![Railway](https://img.shields.io/badge/deploy-Railway-0B0D0E.svg?logo=railway&logoColor=white)](https://railway.com)
[![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64.svg?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Personal calorie & sport coach as an MCP server.
> Log meals, workouts and body-weight in plain English from any MCP client (Claude, Cursor, …) and get daily / multi-day summaries.

**Why?** Most calorie trackers are tedious mobile apps. With this MCP server you just tell Claude *"I had a chicken caesar salad for lunch, ~600 kcal"* and your data lands in your own Postgres on Railway. No third-party app, your data, your numbers.

Stack: [FastMCP](https://gofastmcp.com) · [SQLModel](https://sqlmodel.tiangolo.com) · Postgres · Railway
Auth: GitHub OAuth (single-user allowlist)

## Tools exposed

| Tool          | What it does                                                |
| ------------- | ----------------------------------------------------------- |
| `meals`       | `log` / `update` / `delete` / `list` meals (kcal + macros)  |
| `workouts`    | `log` / `update` / `delete` / `list` workouts (kcal burned) |
| `weights`     | `log` / `update` / `delete` / `list` body-weight entries    |
| `get_summary` | Daily aggregates for one date (Europe/Paris)                |
| `get_history` | Per-day aggregates for the last N days                      |

## Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- `bash`, `make`, `curl` (preinstalled on macOS / Linux)
- A [GitHub](https://github.com) account
- A [Railway](https://railway.com) account — expect ~$5/month for hobby usage (1 service + 1 Postgres)

---

## Quickstart

### 1. Clone & install deps

```bash
git clone https://github.com/ethansmadjaa/coach-mcp.git
cd coach-mcp
uv sync
```

### 2. Provision Railway resources

```bash
make provision   # installs Railway CLI if missing, logs you in,
                 # then creates the project, Postgres and the service
make domain      # generates the public URL and writes it to .env as BASE_URL
```

### 3. Create the GitHub OAuth App

Open [github.com/settings/applications/new](https://github.com/settings/applications/new):

- **Homepage URL**: `https://<your-railway-domain>`
- **Authorization callback URL**: `https://<your-railway-domain>/auth/callback`

Note the **Client ID** and generate a **Client Secret**.

### 4. Fill in `.env`

```bash
make pull-env    # pulls DATABASE_URL & PORT from Railway into .env
```

Then open `.env` and fill the remaining values:

```dotenv
GITHUB_CLIENT_ID=Ov23li...
GITHUB_CLIENT_SECRET=...
ALLOWED_GITHUB_LOGIN=your-github-username
# BASE_URL is already filled by `make domain` above
```

> ⚠️ `ALLOWED_GITHUB_LOGIN` is **case-sensitive** and must match your GitHub username exactly.

### 5. Deploy

```bash
make push-env    # sync .env → Railway
make deploy      # build & deploy from current code
```

### 6. Connect from an MCP client

**claude.ai** → Settings → Connectors → Add custom connector
**Claude Desktop** → Settings → Developer → MCP servers
**Cursor** → Settings → MCP

- **URL**: `https://<your-railway-domain>/mcp/`
- Auth is handled automatically via OAuth (you'll be redirected to GitHub)

---

## Local development

```bash
make help        # list all available targets
make dev         # run server at http://localhost:8000 (uses .env)
make logs        # tail Railway logs
make check       # lint + typecheck
make fix         # auto-fix lint + format
make pull-env    # overwrite .env with Railway values
```

The Postgres schema is created automatically on server start — no manual migration needed.

## How auth works

The server runs FastMCP's [GitHub OAuth proxy](https://gofastmcp.com/servers/auth/oauth-proxy): MCP clients discover the OAuth flow via `/.well-known/oauth-authorization-server`, get redirected to GitHub, and only users whose login matches `ALLOWED_GITHUB_LOGIN` are granted access.

## Configuration as code

Build & deploy config lives in [`railway.toml`](railway.toml). Anything in there overrides the Railway dashboard. See [Railway config-as-code docs](https://docs.railway.com/reference/config-as-code).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `redirect_uri_mismatch` after GitHub login | Your `BASE_URL` and the GitHub App callback URL don't match — re-check both have `/auth/callback` |
| 401 on every request even after successful login | `ALLOWED_GITHUB_LOGIN` doesn't match your GitHub username (case-sensitive) |
| Healthcheck fails on Railway after deploy | `BASE_URL` is wrong — must match the Railway-generated domain exactly |
| `KeyError: GITHUB_CLIENT_ID` at boot | Forgot `make push-env` before `make deploy` |

## License

MIT
