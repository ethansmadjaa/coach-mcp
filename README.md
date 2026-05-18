# Coach MCP

> Personal calorie & sport coach as an MCP server.
> Log meals, workouts and body-weight from any MCP-compatible client (Claude, Cursor, …) and get daily summaries.

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
                 # then creates the project, Postgres and service
make domain      # generates the public URL — copy it
```

The CLI auto-installer expects `bash`. See [docs.railway.com/cli](https://docs.railway.com/cli) for alternative install methods.

### 3. Create the GitHub OAuth App

Open [github.com/settings/applications/new](https://github.com/settings/applications/new):

- **Homepage URL**: `https://<your-railway-domain>`
- **Authorization callback URL**: `https://<your-railway-domain>/auth/callback`

Note the **Client ID** and generate a **Client Secret**.

### 4. Fill in `.env`

```bash
cp .env.example .env
make pull-env    # pulls DATABASE_URL & PORT from Railway
```

Then open `.env` and fill the remaining values:

```dotenv
GITHUB_CLIENT_ID=Ov23li...
GITHUB_CLIENT_SECRET=...
ALLOWED_GITHUB_LOGIN=your-github-username
BASE_URL=https://<your-railway-domain>
```

### 5. Deploy

```bash
make push-env    # sync .env → Railway
make deploy      # build & deploy from current code
```

### 6. Connect from Claude

`claude.ai` → **Settings → Connectors → Add custom connector**

- **URL**: `https://<your-railway-domain>/mcp/`
- Auth is handled automatically (you'll be redirected to GitHub)

---

## Local development

```bash
make dev         # run server at http://localhost:8000 (uses .env)
make logs        # tail Railway logs
make check       # lint + typecheck
make fix         # auto-fix lint + format
make pull-env    # overwrite .env with Railway values
```

The Postgres schema is created automatically on server start — no manual migration needed.

## How auth works

The server runs FastMCP's [GitHub OAuth proxy](https://gofastmcp.com/servers/auth/oauth-proxy): MCP clients (claude.ai, Cursor, …) discover the OAuth flow via `/.well-known/oauth-authorization-server`, get redirected to GitHub, and only users whose login matches `ALLOWED_GITHUB_LOGIN` are granted access.

## Configuration as code

Build & deploy config lives in [`railway.toml`](railway.toml). Anything in there overrides the Railway dashboard. See [Railway config-as-code docs](https://docs.railway.com/reference/config-as-code).

## License

MIT
