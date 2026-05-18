SERVICE = coach-mcp

.PHONY: dev pull-env lint format typecheck check fix logs deploy

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

deploy:
	git push
