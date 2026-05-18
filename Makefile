SHELL := /bin/bash

SERVICE = coach-mcp
PROJECT = coach-mcp

.PHONY: init check-cli provision push-env deploy domain dev pull-env lint format typecheck check fix logs

# ────────────────────────────────────────────────────────────────────
# One-shot bootstrap: install CLI → login → provision → domain → push .env → deploy.
# Prerequisite: .env filled in (copy from .env.example)
# ────────────────────────────────────────────────────────────────────
init: check-cli provision domain push-env deploy
	@echo ""
	@echo "✅ Deployed. Your MCP server is live at the BASE_URL printed above."
	@echo "   Don't forget to update your GitHub OAuth App's callback URL to <BASE_URL>/auth/callback"

check-cli:
	@if ! command -v railway >/dev/null 2>&1; then \
		echo "→ Railway CLI not found. Installing..."; \
		bash <(curl -fsSL railway.com/install.sh) --agents -y; \
	else \
		echo "✓ Railway CLI installed ($$(railway --version))\n\n\n"; \
	fi
	@if ! railway whoami >/dev/null 2>&1; then \
		echo "→ Not logged in. Launching browser..."; \
		railway login; \
	else \
		railway whoami; \
	fi

provision: check-cli
	@echo "→ Creating Railway project & services..."
	railway init -n $(PROJECT) || true
	railway add --database postgres -y || true
	railway add --service $(SERVICE) -y || true
	railway service $(SERVICE)

domain:
	@echo "→ Generating public domain..."
	railway domain --service $(SERVICE) || true
	@echo "→ Update BASE_URL in .env with the domain above, then re-run 'make push-env deploy'"

push-env:
	@echo "→ Pushing .env to Railway..."
	@grep -E '^(GITHUB_CLIENT_ID|GITHUB_CLIENT_SECRET|BASE_URL|ALLOWED_GITHUB_LOGIN)=' .env | \
		while IFS= read -r line; do \
			railway variable set "$$line" --service $(SERVICE) --skip-deploys; \
		done

deploy:
	railway up --service $(SERVICE) --detach

# ────────────────────────────────────────────────────────────────────
# Day-to-day
# ────────────────────────────────────────────────────────────────────
dev:
	uv run python main.py

pull-env:
	railway variables --service $(SERVICE) --kv > .env

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uvx ty check

check: lint typecheck

fix:
	uv run ruff check . --fix && uv run ruff format .

logs:
	railway logs --service $(SERVICE)
