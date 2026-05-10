import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    bearer_token: str
    port: int


def load_settings() -> Settings:
    load_dotenv()
    try:
        database_url = os.environ["DATABASE_URL"]
        bearer_token = os.environ["MCP_BEARER_TOKEN"]
    except KeyError as exc:
        raise RuntimeError(f"missing required env var: {exc.args[0]}") from exc
    port = int(os.environ.get("PORT", "8000"))
    return Settings(database_url=database_url, bearer_token=bearer_token, port=port)
