from typing import Any
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from sqlalchemy.engine import Engine

from coach.config import Settings
from coach.db import make_engine, session_for
from coach.ops.meals import handle_meals
from coach.ops.workouts import handle_workouts
from coach.ops.weights import handle_weights
from coach.ops.summary import get_summary, get_history


def build_server(settings: Settings, engine: Engine | None = None) -> FastMCP:
    eng = engine or make_engine(settings)

    auth = StaticTokenVerifier(
        tokens={
            settings.bearer_token: {
                "client_id": "owner",
                "scopes": ["coach"],
            }
        },
        required_scopes=["coach"],
    )

    mcp = FastMCP("Calorie Coach", auth=auth)

    @mcp.tool(
        name="meals",
        description=(
            "Log/update/delete/list meals. Pass {op: 'log'|'update'|'delete'|'list', ...}. "
            "log: description, kcal, source ('estimated'|'exact'), eaten_at?, protein_g?, carbs_g?, fat_g?. "
            "update: id + any fields. delete: id. list: from?, to? (ISO date or datetime)."
        ),
    )
    def meals_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_meals(session, payload)

    @mcp.tool(
        name="workouts",
        description=(
            "Log/update/delete/list workouts. Pass {op: 'log'|'update'|'delete'|'list', ...}. "
            "log: type, duration_min, kcal_burned, source, done_at?, notes?. "
            "update: id + any fields. delete: id. list: from?, to?."
        ),
    )
    def workouts_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_workouts(session, payload)

    @mcp.tool(
        name="weights",
        description=(
            "Log/update/delete/list body-weight measurements. "
            "log: kg, measured_at?. update: id + any fields. delete: id. list: from?, to?."
        ),
    )
    def weights_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_weights(session, payload)

    @mcp.tool(
        name="get_summary",
        description=(
            "Daily aggregates for one date (YYYY-MM-DD; default today, Europe/Paris). "
            "Returns kcal_in, kcal_burned, kcal_net, macros, latest_weight_kg, "
            "estimated_kcal_ratio (0..1, null if no meals)."
        ),
    )
    def get_summary_tool(date: str | None = None) -> Any:
        with session_for(eng) as session:
            return get_summary(session, date=date)

    @mcp.tool(
        name="get_history",
        description="Per-day aggregates for the last N days (Europe/Paris).",
    )
    def get_history_tool(days: int) -> Any:
        with session_for(eng) as session:
            return get_history(session, days=days)

    return mcp
