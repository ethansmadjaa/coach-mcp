from coach.config import load_settings
from coach.server import build_server


def main() -> None:
    settings = load_settings()
    mcp = build_server(settings)
    mcp.run(transport="http", host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
