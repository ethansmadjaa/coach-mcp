SHELL := /bin/bash

SERVICE = coach-mcp
PROJECT = coach-mcp

REQUIRED_VARS = GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET BASE_URL ALLOWED_GITHUB_LOGIN

.PHONY: help init check-cli provision push-env deploy domain dev pull-env lint format typecheck check fix logs

## help: list all available make targets
help:
	@echo "Coach MCP — available targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^## / { sub(/^## /, ""); printf "  %s\n", $$0 } /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ────────────────────────────────────────────────────────────────────
# One-shot bootstrap: install CLI → login → provision → domain → push .env → deploy.
# Prerequisite: .env filled in (copy from .env.example)
# ────────────────────────────────────────────────────────────────────

init: check-cli provision domain push-env deploy ## end-to-end bootstrap (requires .env filled)
	@echo ""
	@echo "✅ Deployed. Your MCP server is live at the BASE_URL above."
	@echo "   Don't forget to update your GitHub OAuth App's callback URL to <BASE_URL>/auth/callback"

check-cli: ## install Railway CLI if missing + ensure logged in
	@if ! command -v railway >/dev/null 2>&1; then \
		echo "→ Railway CLI not found. Installing..."; \
		bash <(curl -fsSL railway.com/install.sh) --agents -y; \
	else \
		printf "✓ Railway CLI installed (%s)\n" "$$(railway --version)"; \
	fi
	@if ! railway whoami >/dev/null 2>&1; then \
		echo "→ Not logged in. Launching browser..."; \
		railway login; \
	else \
		railway whoami; \
	fi

provision: check-cli ## create Railway project + Postgres + service
	@if railway status >/dev/null 2>&1; then \
		echo "✓ Project already linked — skipping init."; \
	else \
		echo "→ Creating Railway project..."; \
		railway init -n $(PROJECT); \
	fi
	@echo "→ Adding Postgres (idempotent)..."
	@railway add --database postgres -y 2>/dev/null || echo "  (Postgres already present)"
	@echo "→ Adding service $(SERVICE) (idempotent)..."
	@railway add --service $(SERVICE) -y 2>/dev/null || echo "  ($(SERVICE) already present)"
	@railway service $(SERVICE)

domain: ## generate public Railway domain and write BASE_URL to .env
	@echo "→ Generating public domain..."
	@URL=$$(railway domain --service $(SERVICE) --json 2>/dev/null | grep -oE 'https://[^"]+' | head -1); \
	if [ -z "$$URL" ]; then \
		echo "❌ Failed to read domain from Railway."; exit 1; \
	fi; \
	echo "✓ Domain: $$URL"; \
	if [ ! -f .env ]; then cp .env.example .env; fi; \
	if grep -q '^BASE_URL=' .env; then \
		sed -i.bak "s|^BASE_URL=.*|BASE_URL=$$URL|" .env && rm -f .env.bak; \
	else \
		echo "BASE_URL=$$URL" >> .env; \
	fi; \
	echo "✓ BASE_URL written to .env"

push-env: ## push .env values to Railway
	@for v in $(REQUIRED_VARS); do \
		if ! grep -qE "^$$v=.+" .env 2>/dev/null; then \
			echo "❌ $$v is missing or empty in .env — fill it before running push-env."; \
			exit 1; \
		fi; \
	done
	@echo "→ Pushing .env to Railway..."
	@grep -E '^($(shell echo $(REQUIRED_VARS) | tr ' ' '|'))=' .env | \
		while IFS= read -r line; do \
			railway variable set "$$line" --service $(SERVICE) --skip-deploys; \
		done

deploy: ## build and deploy current code to Railway
	railway up --service $(SERVICE) --detach

# ────────────────────────────────────────────────────────────────────
# Day-to-day
# ────────────────────────────────────────────────────────────────────

dev: ## run server locally with .env
	uv run python main.py

pull-env: ## overwrite .env with Railway values
	railway variables --service $(SERVICE) --kv > .env

lint: ## run ruff linter
	uv run ruff check .

format: ## format code with ruff
	uv run ruff format .

typecheck: ## run ty type-checker
	uvx ty check

check: lint typecheck ## lint + typecheck

fix: ## auto-fix lint issues + format
	uv run ruff check . --fix && uv run ruff format .

logs: ## tail Railway logs for the service
	railway logs --service $(SERVICE)
