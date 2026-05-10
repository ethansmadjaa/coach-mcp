# Calorie & Sport Coach MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a remote FastMCP server that journals meals, workouts, and weight to Neon Postgres, exposing 5 entity-grouped tools to Claude over HTTP with bearer-token auth, deployable to Railway.

**Architecture:** FastMCP (Python 3.13) serves as a stateless HTTP MCP. SQLModel maps three append-mostly tables (meals, workouts, weights) over Neon's pooled endpoint. Each entity is a single MCP tool taking a Pydantic discriminated `op` union (`log` / `update` / `delete` / `list`); two extra read tools (`get_summary`, `get_history`) provide aggregates. All "today / this week" math is computed in `Europe/Paris`. Profile and goals live in Claude's context, not in the DB.

**Tech Stack:** Python 3.13, FastMCP ≥ 3.2.4, SQLModel, psycopg (v3), Neon Postgres, pytest, Railway, uv.

**Source spec:** [`docs/superpowers/specs/2026-05-10-calorie-coach-mcp-design.md`](../specs/2026-05-10-calorie-coach-mcp-design.md)

---

## File Structure

```
.
├── main.py                          # entry point; constructs FastMCP, registers tools, runs HTTP server
├── pyproject.toml                   # deps: fastmcp, sqlmodel, psycopg[binary], pydantic, python-dotenv, pytest, freezegun
├── .env.example                     # template for DATABASE_URL, MCP_BEARER_TOKEN, PORT
├── Procfile                         # Railway start command
├── init_db.sql                      # one-shot DDL: 3 CREATE TABLE statements
├── src/
│   └── coach/
│       ├── __init__.py
│       ├── config.py                # env loading, settings dataclass
│       ├── db.py                    # SQLModel engine + session factory
│       ├── models.py                # SQLModel table classes: Meal, Workout, Weight
│       ├── time.py                  # Europe/Paris day-window helpers
│       ├── auth.py                  # bearer token middleware/check
│       ├── ops/
│       │   ├── __init__.py
│       │   ├── payloads.py          # Pydantic discriminated union payloads (LogMeal, UpdateMeal, ...)
│       │   ├── meals.py             # dispatch + handlers for the meals tool
│       │   ├── workouts.py          # dispatch + handlers for the workouts tool
│       │   ├── weights.py           # dispatch + handlers for the weights tool
│       │   └── summary.py           # get_summary + get_history aggregations
│       └── server.py                # builds FastMCP, wires the 5 tools, applies auth
└── tests/
    ├── conftest.py                  # in-memory SQLite engine fixture, frozen-time fixture
    ├── test_time.py
    ├── test_meals.py
    ├── test_workouts.py
    ├── test_weights.py
    ├── test_summary.py
    └── test_auth.py
```

**Why this layout:** business logic lives in `src/coach/ops/` (one file per entity), so each MCP tool is a thin shim that hands its payload to the right handler. Tests target the handlers directly — no need to spin up an MCP server for unit tests. `server.py` is the only file that knows about FastMCP; everything else is reusable.

---

## Task 1: Project dependencies and layout

**Files:**
- Modify: `pyproject.toml`
- Create: `src/coach/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`

- [ ] **Step 1: Update `pyproject.toml` with all dependencies**

Replace the `[project]` block contents:

```toml
[project]
name = "coach"
version = "0.1.0"
description = "Personal calorie & sport coach MCP server"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastmcp>=3.2.4",
    "sqlmodel>=0.0.22",
    "psycopg[binary]>=3.2",
    "pydantic>=2.9",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "freezegun>=1.5",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.uv]
package = false
```

- [ ] **Step 2: Install deps**

```bash
uv sync --extra dev
```

Expected: lockfile updates, `.venv` populated.

- [ ] **Step 3: Create empty package init files**

```bash
mkdir -p src/coach tests && touch src/coach/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create `.env.example`**

```
DATABASE_URL=postgres://user:pass@host-pooler.neon.tech/dbname?sslmode=require
MCP_BEARER_TOKEN=replace-with-long-random-string
PORT=8000
```

- [ ] **Step 5: Verify pytest discovers the empty test dir**

```bash
uv run pytest
```

Expected: "no tests ran" exit 5 (acceptable here) or exit 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/coach/__init__.py tests/__init__.py .env.example
git commit -m "chore: project layout and dependencies"
```

---

## Task 2: Config loader

**Files:**
- Create: `src/coach/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import os
import pytest
from coach.config import Settings, load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("MCP_BEARER_TOKEN", "tok")
    monkeypatch.setenv("PORT", "9000")
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.database_url == "postgres://x"
    assert s.bearer_token == "tok"
    assert s.port == 9000


def test_load_settings_default_port(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("MCP_BEARER_TOKEN", "tok")
    monkeypatch.delenv("PORT", raising=False)
    assert load_settings().port == 8000


def test_load_settings_missing_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MCP_BEARER_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        load_settings()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError on `coach.config`.

- [ ] **Step 3: Implement**

```python
# src/coach/config.py
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
```

- [ ] **Step 4: Run test, verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/config.py tests/test_config.py
git commit -m "feat(config): typed settings loader from env"
```

---

## Task 3: Time helpers (Europe/Paris day windows)

**Files:**
- Create: `src/coach/time.py`
- Test: `tests/test_time.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_time.py
from datetime import datetime, timezone, date
from freezegun import freeze_time
from coach.time import paris_day_bounds, parse_iso_or_date


@freeze_time("2026-05-10T22:30:00Z")
def test_paris_day_bounds_today_after_midnight_utc():
    # 22:30 UTC on May 10 = 00:30 May 11 in Paris (CEST = UTC+2)
    start, end = paris_day_bounds(None)
    assert start == datetime(2026, 5, 10, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 11, 22, 0, tzinfo=timezone.utc)


def test_paris_day_bounds_explicit_date():
    start, end = paris_day_bounds(date(2026, 5, 10))
    # CEST: Paris midnight = 22:00 UTC previous day
    assert start == datetime(2026, 5, 9, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 10, 22, 0, tzinfo=timezone.utc)


def test_paris_day_bounds_winter_date():
    # CET: Paris midnight = 23:00 UTC previous day
    start, end = paris_day_bounds(date(2026, 1, 15))
    assert start == datetime(2026, 1, 14, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)


def test_parse_iso_or_date_accepts_date():
    assert parse_iso_or_date("2026-05-10") == date(2026, 5, 10)


def test_parse_iso_or_date_accepts_datetime():
    parsed = parse_iso_or_date("2026-05-10T12:00:00+02:00")
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_time.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/coach/time.py
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def paris_day_bounds(d: date | None) -> tuple[datetime, datetime]:
    """Return [start, end) UTC bounds for a Paris-local day. d=None means today in Paris."""
    if d is None:
        d = datetime.now(PARIS).date()
    start_local = datetime.combine(d, time.min, tzinfo=PARIS)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def parse_iso_or_date(s: str) -> date | datetime:
    """Parse ISO-8601 datetime, or a bare YYYY-MM-DD date."""
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s)
    return datetime.fromisoformat(s)
```

- [ ] **Step 4: Run test, verify it passes**

```bash
uv run pytest tests/test_time.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/time.py tests/test_time.py
git commit -m "feat(time): Europe/Paris day-window helpers"
```

---

## Task 4: SQLModel tables and engine

**Files:**
- Create: `src/coach/models.py`
- Create: `src/coach/db.py`
- Create: `init_db.sql`
- Create: `tests/conftest.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the conftest fixture**

```python
# tests/conftest.py
import pytest
from sqlmodel import SQLModel, Session, create_engine


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_models.py
from datetime import datetime, timezone
from decimal import Decimal
from sqlmodel import select
from coach.models import Meal, Workout, Weight


def test_meal_round_trip(session):
    m = Meal(
        eaten_at=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
        description="poke bowl",
        kcal=Decimal("650.0"),
        protein_g=Decimal("40"),
        carbs_g=Decimal("70"),
        fat_g=Decimal("20"),
        source="estimated",
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    assert m.id is not None
    fetched = session.exec(select(Meal).where(Meal.id == m.id)).one()
    assert fetched.description == "poke bowl"
    assert fetched.kcal == Decimal("650.0")


def test_workout_round_trip(session):
    w = Workout(
        done_at=datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc),
        type="running",
        duration_min=45,
        kcal_burned=Decimal("420"),
        source="exact",
        notes="easy pace",
    )
    session.add(w)
    session.commit()
    session.refresh(w)
    assert w.id is not None
    assert w.duration_min == 45


def test_weight_round_trip(session):
    weight = Weight(
        measured_at=datetime(2026, 5, 10, 7, 0, tzinfo=timezone.utc),
        kg=Decimal("78.4"),
    )
    session.add(weight)
    session.commit()
    session.refresh(weight)
    assert weight.id is not None
    assert weight.kg == Decimal("78.4")
```

- [ ] **Step 3: Run test, verify it fails**

```bash
uv run pytest tests/test_models.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement models**

```python
# src/coach/models.py
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


Source = Literal["estimated", "exact"]


class Meal(SQLModel, table=True):
    __tablename__ = "meals"
    id: int | None = Field(default=None, primary_key=True)
    eaten_at: datetime
    description: str
    kcal: Decimal
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    source: Source
    created_at: datetime = Field(default_factory=_utcnow)


class Workout(SQLModel, table=True):
    __tablename__ = "workouts"
    id: int | None = Field(default=None, primary_key=True)
    done_at: datetime
    type: str
    duration_min: int
    kcal_burned: Decimal
    source: Source
    notes: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Weight(SQLModel, table=True):
    __tablename__ = "weights"
    id: int | None = Field(default=None, primary_key=True)
    measured_at: datetime
    kg: Decimal
    created_at: datetime = Field(default_factory=_utcnow)
```

- [ ] **Step 5: Implement engine factory**

```python
# src/coach/db.py
from sqlmodel import Session, create_engine
from sqlalchemy.engine import Engine
from coach.config import Settings


def make_engine(settings: Settings) -> Engine:
    # SQLAlchemy expects postgresql:// not postgres://
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


def session_for(engine: Engine) -> Session:
    return Session(engine)
```

- [ ] **Step 6: Write `init_db.sql`**

```sql
-- init_db.sql
create table if not exists meals (
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

create table if not exists workouts (
  id           bigserial primary key,
  done_at      timestamptz not null,
  type         text not null,
  duration_min integer not null,
  kcal_burned  numeric(7,1) not null,
  source       text not null check (source in ('estimated','exact')),
  notes        text,
  created_at   timestamptz not null default now()
);

create table if not exists weights (
  id           bigserial primary key,
  measured_at  timestamptz not null,
  kg           numeric(5,2) not null,
  created_at   timestamptz not null default now()
);
```

- [ ] **Step 7: Run tests, verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add src/coach/models.py src/coach/db.py init_db.sql tests/conftest.py tests/test_models.py
git commit -m "feat(db): SQLModel tables, engine factory, init_db.sql"
```

---

## Task 5: Pydantic discriminated payloads

**Files:**
- Create: `src/coach/ops/__init__.py`
- Create: `src/coach/ops/payloads.py`
- Test: `tests/test_payloads.py`

- [ ] **Step 1: Empty package init**

```bash
touch src/coach/ops/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_payloads.py
from decimal import Decimal
import pytest
from pydantic import ValidationError, TypeAdapter
from coach.ops.payloads import MealsPayload, WorkoutsPayload, WeightsPayload


def test_meals_log_valid():
    p = TypeAdapter(MealsPayload).validate_python({
        "op": "log",
        "description": "poke bowl",
        "kcal": "650",
        "source": "estimated",
    })
    assert p.op == "log"
    assert p.kcal == Decimal("650")


def test_meals_log_rejects_negative_kcal():
    with pytest.raises(ValidationError):
        TypeAdapter(MealsPayload).validate_python({
            "op": "log",
            "description": "x",
            "kcal": -1,
            "source": "exact",
        })


def test_meals_update_partial():
    p = TypeAdapter(MealsPayload).validate_python({
        "op": "update",
        "id": 1,
        "kcal": 700,
    })
    assert p.op == "update"
    assert p.id == 1
    assert p.kcal == Decimal("700")
    assert p.description is None


def test_meals_delete():
    p = TypeAdapter(MealsPayload).validate_python({"op": "delete", "id": 5})
    assert p.op == "delete"


def test_meals_list_dates_optional():
    p = TypeAdapter(MealsPayload).validate_python({"op": "list"})
    assert p.op == "list"
    assert p.from_ is None


def test_workouts_log_valid():
    p = TypeAdapter(WorkoutsPayload).validate_python({
        "op": "log",
        "type": "run",
        "duration_min": 45,
        "kcal_burned": 420,
        "source": "exact",
    })
    assert p.op == "log"
    assert p.duration_min == 45


def test_weights_log_valid():
    p = TypeAdapter(WeightsPayload).validate_python({"op": "log", "kg": "78.4"})
    assert p.kg == Decimal("78.4")


def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(MealsPayload).validate_python({"op": "nope"})
```

- [ ] **Step 3: Run test, verify it fails**

```bash
uv run pytest tests/test_payloads.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement payloads**

```python
# src/coach/ops/payloads.py
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

Source = Literal["estimated", "exact"]


# --- meals ---

class LogMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["log"]
    description: str
    kcal: Decimal = Field(ge=0)
    source: Source
    eaten_at: datetime | None = None
    protein_g: Decimal | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = Field(default=None, ge=0)
    fat_g: Decimal | None = Field(default=None, ge=0)


class UpdateMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update"]
    id: int
    description: str | None = None
    kcal: Decimal | None = Field(default=None, ge=0)
    source: Source | None = None
    eaten_at: datetime | None = None
    protein_g: Decimal | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = Field(default=None, ge=0)
    fat_g: Decimal | None = Field(default=None, ge=0)


class DeleteMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["delete"]
    id: int


class ListMeals(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    op: Literal["list"]
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


MealsPayload = Annotated[
    Union[LogMeal, UpdateMeal, DeleteMeal, ListMeals],
    Field(discriminator="op"),
]


# --- workouts ---

class LogWorkout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["log"]
    type: str
    duration_min: int = Field(gt=0)
    kcal_burned: Decimal = Field(ge=0)
    source: Source
    done_at: datetime | None = None
    notes: str | None = None


class UpdateWorkout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update"]
    id: int
    type: str | None = None
    duration_min: int | None = Field(default=None, gt=0)
    kcal_burned: Decimal | None = Field(default=None, ge=0)
    source: Source | None = None
    done_at: datetime | None = None
    notes: str | None = None


class DeleteWorkout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["delete"]
    id: int


class ListWorkouts(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    op: Literal["list"]
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


WorkoutsPayload = Annotated[
    Union[LogWorkout, UpdateWorkout, DeleteWorkout, ListWorkouts],
    Field(discriminator="op"),
]


# --- weights ---

class LogWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["log"]
    kg: Decimal = Field(gt=0)
    measured_at: datetime | None = None


class UpdateWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update"]
    id: int
    kg: Decimal | None = Field(default=None, gt=0)
    measured_at: datetime | None = None


class DeleteWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["delete"]
    id: int


class ListWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    op: Literal["list"]
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


WeightsPayload = Annotated[
    Union[LogWeight, UpdateWeight, DeleteWeight, ListWeights],
    Field(discriminator="op"),
]
```

- [ ] **Step 5: Run test, verify it passes**

```bash
uv run pytest tests/test_payloads.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add src/coach/ops/__init__.py src/coach/ops/payloads.py tests/test_payloads.py
git commit -m "feat(ops): Pydantic discriminated payloads for the 3 entity tools"
```

---

## Task 6: Meals handler

**Files:**
- Create: `src/coach/ops/meals.py`
- Test: `tests/test_meals.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_meals.py
from datetime import datetime, timezone
from decimal import Decimal
from freezegun import freeze_time
from coach.ops.meals import handle_meals


@freeze_time("2026-05-10T10:00:00Z")
def test_log_meal_defaults_eaten_at_to_now(session):
    out = handle_meals(session, {
        "op": "log", "description": "salad", "kcal": 300, "source": "estimated",
    })
    assert out["id"] is not None
    assert out["description"] == "salad"
    assert out["kcal"] == "300"
    assert out["source"] == "estimated"
    assert out["eaten_at"] == "2026-05-10T10:00:00+00:00"


def test_log_meal_with_explicit_eaten_at(session):
    out = handle_meals(session, {
        "op": "log",
        "description": "lunch",
        "kcal": "650.0",
        "source": "exact",
        "eaten_at": "2026-05-10T12:00:00+02:00",
        "protein_g": "40",
    })
    assert out["protein_g"] == "40"


def test_update_meal_partial(session):
    created = handle_meals(session, {
        "op": "log", "description": "x", "kcal": 100, "source": "estimated",
    })
    out = handle_meals(session, {"op": "update", "id": created["id"], "kcal": 200})
    assert out["id"] == created["id"]
    assert out["kcal"] == "200"
    assert out["description"] == "x"


def test_update_meal_unknown_id_raises(session):
    import pytest
    with pytest.raises(LookupError):
        handle_meals(session, {"op": "update", "id": 9999, "kcal": 1})


def test_delete_meal(session):
    created = handle_meals(session, {
        "op": "log", "description": "x", "kcal": 100, "source": "exact",
    })
    out = handle_meals(session, {"op": "delete", "id": created["id"]})
    assert out == {"deleted": created["id"]}
    listed = handle_meals(session, {"op": "list"})
    assert listed == []


def test_list_meals_filters_by_range(session):
    handle_meals(session, {
        "op": "log", "description": "a", "kcal": 1, "source": "exact",
        "eaten_at": "2026-05-08T10:00:00+00:00",
    })
    handle_meals(session, {
        "op": "log", "description": "b", "kcal": 2, "source": "exact",
        "eaten_at": "2026-05-10T10:00:00+00:00",
    })
    out = handle_meals(session, {"op": "list", "from": "2026-05-09", "to": "2026-05-11"})
    assert [m["description"] for m in out] == ["b"]
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_meals.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement handler**

```python
# src/coach/ops/meals.py
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from pydantic import TypeAdapter
from sqlmodel import Session, select
from coach.models import Meal
from coach.ops.payloads import MealsPayload, LogMeal, UpdateMeal, DeleteMeal, ListMeals
from coach.time import paris_day_bounds, parse_iso_or_date

_ADAPTER = TypeAdapter(MealsPayload)


def handle_meals(session: Session, raw: dict[str, Any]) -> Any:
    payload = _ADAPTER.validate_python(raw)
    if isinstance(payload, LogMeal):
        return _log(session, payload)
    if isinstance(payload, UpdateMeal):
        return _update(session, payload)
    if isinstance(payload, DeleteMeal):
        return _delete(session, payload)
    if isinstance(payload, ListMeals):
        return _list(session, payload)
    raise AssertionError("unreachable")


def _serialize(m: Meal) -> dict[str, Any]:
    return {
        "id": m.id,
        "eaten_at": m.eaten_at.isoformat(),
        "description": m.description,
        "kcal": str(m.kcal),
        "protein_g": None if m.protein_g is None else str(m.protein_g),
        "carbs_g": None if m.carbs_g is None else str(m.carbs_g),
        "fat_g": None if m.fat_g is None else str(m.fat_g),
        "source": m.source,
        "created_at": m.created_at.isoformat(),
    }


def _log(session: Session, p: LogMeal) -> dict[str, Any]:
    m = Meal(
        eaten_at=p.eaten_at or datetime.now(timezone.utc),
        description=p.description,
        kcal=p.kcal,
        protein_g=p.protein_g,
        carbs_g=p.carbs_g,
        fat_g=p.fat_g,
        source=p.source,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return _serialize(m)


def _update(session: Session, p: UpdateMeal) -> dict[str, Any]:
    m = session.get(Meal, p.id)
    if m is None:
        raise LookupError(f"meal {p.id} not found")
    for field in ("description", "kcal", "source", "eaten_at", "protein_g", "carbs_g", "fat_g"):
        v = getattr(p, field)
        if v is not None:
            setattr(m, field, v)
    session.add(m)
    session.commit()
    session.refresh(m)
    return _serialize(m)


def _delete(session: Session, p: DeleteMeal) -> dict[str, Any]:
    m = session.get(Meal, p.id)
    if m is None:
        raise LookupError(f"meal {p.id} not found")
    session.delete(m)
    session.commit()
    return {"deleted": p.id}


def _list(session: Session, p: ListMeals) -> list[dict[str, Any]]:
    stmt = select(Meal).order_by(Meal.eaten_at)
    if p.from_ is not None:
        f = parse_iso_or_date(p.from_)
        if hasattr(f, "hour"):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Meal.eaten_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if hasattr(t, "hour"):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Meal.eaten_at < end)
    return [_serialize(m) for m in session.exec(stmt).all()]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_meals.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/ops/meals.py tests/test_meals.py
git commit -m "feat(meals): log/update/delete/list handlers"
```

---

## Task 7: Workouts handler

**Files:**
- Create: `src/coach/ops/workouts.py`
- Test: `tests/test_workouts.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_workouts.py
import pytest
from freezegun import freeze_time
from coach.ops.workouts import handle_workouts


@freeze_time("2026-05-10T18:00:00Z")
def test_log_workout_defaults_done_at(session):
    out = handle_workouts(session, {
        "op": "log", "type": "run", "duration_min": 30, "kcal_burned": 300, "source": "estimated",
    })
    assert out["type"] == "run"
    assert out["duration_min"] == 30
    assert out["kcal_burned"] == "300"
    assert out["done_at"] == "2026-05-10T18:00:00+00:00"


def test_update_workout_notes(session):
    created = handle_workouts(session, {
        "op": "log", "type": "run", "duration_min": 30, "kcal_burned": 300, "source": "exact",
    })
    out = handle_workouts(session, {"op": "update", "id": created["id"], "notes": "easy"})
    assert out["notes"] == "easy"


def test_delete_workout(session):
    created = handle_workouts(session, {
        "op": "log", "type": "run", "duration_min": 30, "kcal_burned": 300, "source": "exact",
    })
    out = handle_workouts(session, {"op": "delete", "id": created["id"]})
    assert out == {"deleted": created["id"]}


def test_delete_workout_unknown(session):
    with pytest.raises(LookupError):
        handle_workouts(session, {"op": "delete", "id": 9999})


def test_list_workouts_range(session):
    handle_workouts(session, {
        "op": "log", "type": "run", "duration_min": 30, "kcal_burned": 300, "source": "exact",
        "done_at": "2026-05-08T18:00:00+00:00",
    })
    handle_workouts(session, {
        "op": "log", "type": "muscu", "duration_min": 60, "kcal_burned": 400, "source": "exact",
        "done_at": "2026-05-10T18:00:00+00:00",
    })
    out = handle_workouts(session, {"op": "list", "from": "2026-05-09", "to": "2026-05-11"})
    assert [w["type"] for w in out] == ["muscu"]
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_workouts.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/coach/ops/workouts.py
from datetime import datetime, timezone
from typing import Any
from pydantic import TypeAdapter
from sqlmodel import Session, select
from coach.models import Workout
from coach.ops.payloads import (
    WorkoutsPayload, LogWorkout, UpdateWorkout, DeleteWorkout, ListWorkouts,
)
from coach.time import paris_day_bounds, parse_iso_or_date

_ADAPTER = TypeAdapter(WorkoutsPayload)


def handle_workouts(session: Session, raw: dict[str, Any]) -> Any:
    payload = _ADAPTER.validate_python(raw)
    if isinstance(payload, LogWorkout):
        return _log(session, payload)
    if isinstance(payload, UpdateWorkout):
        return _update(session, payload)
    if isinstance(payload, DeleteWorkout):
        return _delete(session, payload)
    if isinstance(payload, ListWorkouts):
        return _list(session, payload)
    raise AssertionError("unreachable")


def _serialize(w: Workout) -> dict[str, Any]:
    return {
        "id": w.id,
        "done_at": w.done_at.isoformat(),
        "type": w.type,
        "duration_min": w.duration_min,
        "kcal_burned": str(w.kcal_burned),
        "source": w.source,
        "notes": w.notes,
        "created_at": w.created_at.isoformat(),
    }


def _log(session: Session, p: LogWorkout) -> dict[str, Any]:
    w = Workout(
        done_at=p.done_at or datetime.now(timezone.utc),
        type=p.type,
        duration_min=p.duration_min,
        kcal_burned=p.kcal_burned,
        source=p.source,
        notes=p.notes,
    )
    session.add(w)
    session.commit()
    session.refresh(w)
    return _serialize(w)


def _update(session: Session, p: UpdateWorkout) -> dict[str, Any]:
    w = session.get(Workout, p.id)
    if w is None:
        raise LookupError(f"workout {p.id} not found")
    for field in ("type", "duration_min", "kcal_burned", "source", "done_at", "notes"):
        v = getattr(p, field)
        if v is not None:
            setattr(w, field, v)
    session.add(w)
    session.commit()
    session.refresh(w)
    return _serialize(w)


def _delete(session: Session, p: DeleteWorkout) -> dict[str, Any]:
    w = session.get(Workout, p.id)
    if w is None:
        raise LookupError(f"workout {p.id} not found")
    session.delete(w)
    session.commit()
    return {"deleted": p.id}


def _list(session: Session, p: ListWorkouts) -> list[dict[str, Any]]:
    stmt = select(Workout).order_by(Workout.done_at)
    if p.from_ is not None:
        f = parse_iso_or_date(p.from_)
        if hasattr(f, "hour"):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Workout.done_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if hasattr(t, "hour"):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Workout.done_at < end)
    return [_serialize(w) for w in session.exec(stmt).all()]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_workouts.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/ops/workouts.py tests/test_workouts.py
git commit -m "feat(workouts): log/update/delete/list handlers"
```

---

## Task 8: Weights handler

**Files:**
- Create: `src/coach/ops/weights.py`
- Test: `tests/test_weights.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_weights.py
import pytest
from freezegun import freeze_time
from coach.ops.weights import handle_weights


@freeze_time("2026-05-10T07:00:00Z")
def test_log_weight_defaults_measured_at(session):
    out = handle_weights(session, {"op": "log", "kg": "78.4"})
    assert out["kg"] == "78.4"
    assert out["measured_at"] == "2026-05-10T07:00:00+00:00"


def test_update_weight(session):
    created = handle_weights(session, {"op": "log", "kg": "80"})
    out = handle_weights(session, {"op": "update", "id": created["id"], "kg": "79.5"})
    assert out["kg"] == "79.5"


def test_delete_weight_unknown(session):
    with pytest.raises(LookupError):
        handle_weights(session, {"op": "delete", "id": 1})


def test_list_weights_returns_all_when_no_range(session):
    handle_weights(session, {"op": "log", "kg": "78.0", "measured_at": "2026-05-08T07:00:00+00:00"})
    handle_weights(session, {"op": "log", "kg": "77.5", "measured_at": "2026-05-10T07:00:00+00:00"})
    out = handle_weights(session, {"op": "list"})
    assert len(out) == 2
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_weights.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/coach/ops/weights.py
from datetime import datetime, timezone
from typing import Any
from pydantic import TypeAdapter
from sqlmodel import Session, select
from coach.models import Weight
from coach.ops.payloads import (
    WeightsPayload, LogWeight, UpdateWeight, DeleteWeight, ListWeights,
)
from coach.time import paris_day_bounds, parse_iso_or_date

_ADAPTER = TypeAdapter(WeightsPayload)


def handle_weights(session: Session, raw: dict[str, Any]) -> Any:
    payload = _ADAPTER.validate_python(raw)
    if isinstance(payload, LogWeight):
        return _log(session, payload)
    if isinstance(payload, UpdateWeight):
        return _update(session, payload)
    if isinstance(payload, DeleteWeight):
        return _delete(session, payload)
    if isinstance(payload, ListWeights):
        return _list(session, payload)
    raise AssertionError("unreachable")


def _serialize(w: Weight) -> dict[str, Any]:
    return {
        "id": w.id,
        "measured_at": w.measured_at.isoformat(),
        "kg": str(w.kg),
        "created_at": w.created_at.isoformat(),
    }


def _log(session: Session, p: LogWeight) -> dict[str, Any]:
    w = Weight(measured_at=p.measured_at or datetime.now(timezone.utc), kg=p.kg)
    session.add(w)
    session.commit()
    session.refresh(w)
    return _serialize(w)


def _update(session: Session, p: UpdateWeight) -> dict[str, Any]:
    w = session.get(Weight, p.id)
    if w is None:
        raise LookupError(f"weight {p.id} not found")
    if p.kg is not None:
        w.kg = p.kg
    if p.measured_at is not None:
        w.measured_at = p.measured_at
    session.add(w)
    session.commit()
    session.refresh(w)
    return _serialize(w)


def _delete(session: Session, p: DeleteWeight) -> dict[str, Any]:
    w = session.get(Weight, p.id)
    if w is None:
        raise LookupError(f"weight {p.id} not found")
    session.delete(w)
    session.commit()
    return {"deleted": p.id}


def _list(session: Session, p: ListWeights) -> list[dict[str, Any]]:
    stmt = select(Weight).order_by(Weight.measured_at)
    if p.from_ is not None:
        f = parse_iso_or_date(p.from_)
        if hasattr(f, "hour"):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Weight.measured_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if hasattr(t, "hour"):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Weight.measured_at < end)
    return [_serialize(w) for w in session.exec(stmt).all()]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_weights.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/ops/weights.py tests/test_weights.py
git commit -m "feat(weights): log/update/delete/list handlers"
```

---

## Task 9: Summary aggregation (`get_summary` + `get_history`)

**Files:**
- Create: `src/coach/ops/summary.py`
- Test: `tests/test_summary.py`

The summary shape, per day:

```json
{
  "date": "2026-05-10",
  "kcal_in": "1500",
  "kcal_burned": "420",
  "kcal_net": "1080",
  "protein_g": "120",
  "carbs_g": "150",
  "fat_g": "50",
  "latest_weight_kg": "78.4",
  "estimated_kcal_ratio": "0.4"
}
```

`estimated_kcal_ratio` = sum of estimated kcal in / total kcal in (0..1). `null` if no meals.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_summary.py
from decimal import Decimal
from freezegun import freeze_time
from coach.ops.meals import handle_meals
from coach.ops.workouts import handle_workouts
from coach.ops.weights import handle_weights
from coach.ops.summary import get_summary, get_history


@freeze_time("2026-05-10T20:00:00Z")
def test_summary_today_aggregates(session):
    handle_meals(session, {
        "op": "log", "description": "breakfast", "kcal": 500, "source": "estimated",
        "protein_g": 30, "carbs_g": 60, "fat_g": 15,
        "eaten_at": "2026-05-10T08:00:00+02:00",
    })
    handle_meals(session, {
        "op": "log", "description": "lunch", "kcal": 1000, "source": "exact",
        "protein_g": 50, "carbs_g": 100, "fat_g": 35,
        "eaten_at": "2026-05-10T13:00:00+02:00",
    })
    handle_workouts(session, {
        "op": "log", "type": "run", "duration_min": 30, "kcal_burned": 300, "source": "exact",
        "done_at": "2026-05-10T07:00:00+02:00",
    })
    handle_weights(session, {"op": "log", "kg": "78.4", "measured_at": "2026-05-10T07:00:00+02:00"})

    out = get_summary(session, date=None)
    assert out["date"] == "2026-05-10"
    assert out["kcal_in"] == "1500"
    assert out["kcal_burned"] == "300"
    assert out["kcal_net"] == "1200"
    assert out["protein_g"] == "80"
    assert out["latest_weight_kg"] == "78.4"
    # 500 estimated / 1500 total
    assert out["estimated_kcal_ratio"] == "0.3333333333333333333333333333"


def test_summary_empty_day(session):
    out = get_summary(session, date="2026-05-10")
    assert out["date"] == "2026-05-10"
    assert out["kcal_in"] == "0"
    assert out["kcal_burned"] == "0"
    assert out["kcal_net"] == "0"
    assert out["latest_weight_kg"] is None
    assert out["estimated_kcal_ratio"] is None


@freeze_time("2026-05-10T20:00:00Z")
def test_history_n_days(session):
    handle_meals(session, {
        "op": "log", "description": "x", "kcal": 100, "source": "exact",
        "eaten_at": "2026-05-08T12:00:00+02:00",
    })
    handle_meals(session, {
        "op": "log", "description": "y", "kcal": 200, "source": "exact",
        "eaten_at": "2026-05-10T12:00:00+02:00",
    })
    out = get_history(session, days=3)
    assert len(out) == 3
    assert [d["date"] for d in out] == ["2026-05-08", "2026-05-09", "2026-05-10"]
    assert out[0]["kcal_in"] == "100"
    assert out[1]["kcal_in"] == "0"
    assert out[2]["kcal_in"] == "200"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_summary.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/coach/ops/summary.py
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import Any
from sqlmodel import Session, select
from coach.models import Meal, Workout, Weight
from coach.time import paris_day_bounds, PARIS


def _aggregate_day(session: Session, d: date_cls) -> dict[str, Any]:
    start, end = paris_day_bounds(d)
    meals = session.exec(
        select(Meal).where(Meal.eaten_at >= start, Meal.eaten_at < end)
    ).all()
    workouts = session.exec(
        select(Workout).where(Workout.done_at >= start, Workout.done_at < end)
    ).all()
    weights = session.exec(
        select(Weight).where(Weight.measured_at >= start, Weight.measured_at < end)
        .order_by(Weight.measured_at.desc())
    ).all()

    kcal_in = sum((m.kcal for m in meals), Decimal(0))
    kcal_burned = sum((w.kcal_burned for w in workouts), Decimal(0))
    protein = sum((m.protein_g or Decimal(0) for m in meals), Decimal(0))
    carbs = sum((m.carbs_g or Decimal(0) for m in meals), Decimal(0))
    fat = sum((m.fat_g or Decimal(0) for m in meals), Decimal(0))

    if meals:
        est = sum((m.kcal for m in meals if m.source == "estimated"), Decimal(0))
        ratio: Decimal | None = est / kcal_in if kcal_in > 0 else Decimal(0)
    else:
        ratio = None

    return {
        "date": d.isoformat(),
        "kcal_in": str(kcal_in),
        "kcal_burned": str(kcal_burned),
        "kcal_net": str(kcal_in - kcal_burned),
        "protein_g": str(protein),
        "carbs_g": str(carbs),
        "fat_g": str(fat),
        "latest_weight_kg": str(weights[0].kg) if weights else None,
        "estimated_kcal_ratio": str(ratio) if ratio is not None else None,
    }


def _resolve_date(d: str | None) -> date_cls:
    if d is None:
        return datetime.now(PARIS).date()
    return date_cls.fromisoformat(d)


def get_summary(session: Session, date: str | None = None) -> dict[str, Any]:
    return _aggregate_day(session, _resolve_date(date))


def get_history(session: Session, days: int) -> list[dict[str, Any]]:
    if days < 1:
        raise ValueError("days must be >= 1")
    today = datetime.now(PARIS).date()
    start = today - timedelta(days=days - 1)
    return [_aggregate_day(session, start + timedelta(days=i)) for i in range(days)]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_summary.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/ops/summary.py tests/test_summary.py
git commit -m "feat(summary): per-day aggregates and history"
```

---

## Task 10: Bearer-token auth check

**Files:**
- Create: `src/coach/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_auth.py
import pytest
from coach.auth import check_bearer


def test_check_bearer_accepts_matching_token():
    check_bearer("Bearer secret", expected="secret")  # no raise


def test_check_bearer_rejects_missing_header():
    with pytest.raises(PermissionError):
        check_bearer(None, expected="secret")


def test_check_bearer_rejects_wrong_scheme():
    with pytest.raises(PermissionError):
        check_bearer("Basic abc", expected="secret")


def test_check_bearer_rejects_wrong_token():
    with pytest.raises(PermissionError):
        check_bearer("Bearer nope", expected="secret")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/coach/auth.py
import hmac


def check_bearer(authorization_header: str | None, *, expected: str) -> None:
    """Raise PermissionError if the header doesn't carry the expected bearer token."""
    if not authorization_header:
        raise PermissionError("missing Authorization header")
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise PermissionError("invalid Authorization scheme")
    if not hmac.compare_digest(parts[1], expected):
        raise PermissionError("invalid bearer token")
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/coach/auth.py tests/test_auth.py
git commit -m "feat(auth): constant-time bearer token check"
```

---

## Task 11: FastMCP server wiring

**Files:**
- Create: `src/coach/server.py`
- Modify: `main.py`

> Caveat: FastMCP's exact API for declaring HTTP transport, accessing per-request headers (for the bearer check), and binding tool input schemas to Pydantic models has evolved. **Before writing this task's code, fetch the current FastMCP docs** (`https://gofastmcp.com/` or `pip show fastmcp` → repo) and adapt the calls below if signatures differ. The shape of the code is correct; the API surface might need tweaking.

- [ ] **Step 1: Write `server.py`**

```python
# src/coach/server.py
from typing import Any
from fastmcp import FastMCP
from sqlalchemy.engine import Engine
from sqlmodel import Session

from coach.config import Settings
from coach.db import make_engine, session_for
from coach.ops.meals import handle_meals
from coach.ops.workouts import handle_workouts
from coach.ops.weights import handle_weights
from coach.ops.summary import get_summary, get_history


def build_server(settings: Settings, engine: Engine | None = None) -> FastMCP:
    eng = engine or make_engine(settings)
    mcp = FastMCP("Calorie Coach")

    def _with_session(fn):
        def wrapper(*args, **kwargs):
            with session_for(eng) as session:
                return fn(session, *args, **kwargs)
        return wrapper

    @mcp.tool(name="meals", description="Log/update/delete/list meals. Pass {op: log|update|delete|list, ...}.")
    def meals_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_meals(session, payload)

    @mcp.tool(name="workouts", description="Log/update/delete/list workouts.")
    def workouts_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_workouts(session, payload)

    @mcp.tool(name="weights", description="Log/update/delete/list weight measurements.")
    def weights_tool(payload: dict[str, Any]) -> Any:
        with session_for(eng) as session:
            return handle_weights(session, payload)

    @mcp.tool(name="get_summary", description="Aggregates for one day (default: today, Europe/Paris).")
    def get_summary_tool(date: str | None = None) -> Any:
        with session_for(eng) as session:
            return get_summary(session, date=date)

    @mcp.tool(name="get_history", description="Per-day aggregates for the last N days.")
    def get_history_tool(days: int) -> Any:
        with session_for(eng) as session:
            return get_history(session, days=days)

    return mcp
```

- [ ] **Step 2: Replace `main.py`**

```python
# main.py
from coach.config import load_settings
from coach.server import build_server


def main() -> None:
    settings = load_settings()
    mcp = build_server(settings)
    # FastMCP's HTTP transport. Verify exact arg names against installed version.
    mcp.run(transport="http", host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-check imports and full test suite**

```bash
uv run python -c "from coach.server import build_server; print('ok')"
uv run pytest -v
```

Expected: `ok` on the first command, all tests green on the second.

- [ ] **Step 4: Verify auth wiring**

FastMCP's HTTP transport supports header-based auth differently across versions. Read its current docs and add the bearer check using whichever extension point it provides (request middleware, auth provider, or wrapping the underlying ASGI app). Add a test once the integration point is identified — skip rather than fake it.

- [ ] **Step 5: Commit**

```bash
git add src/coach/server.py main.py
git commit -m "feat(server): wire 5 MCP tools onto FastMCP HTTP transport"
```

---

## Task 12: Local end-to-end smoke against Neon

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Provision a Neon project**

In the Neon console: create a project, copy the **pooled** connection string (the one with `-pooler` in the host).

- [ ] **Step 2: Apply DDL**

```bash
psql "$DATABASE_URL" -f init_db.sql
```

Expected: `CREATE TABLE` × 3 (or "already exists" notices on re-run).

- [ ] **Step 3: Create local `.env`**

Copy `.env.example` to `.env` and fill in the real `DATABASE_URL` and a long random `MCP_BEARER_TOKEN` (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`). `.env` is gitignored — confirm with `git status`.

- [ ] **Step 4: Run the server**

```bash
uv run python main.py
```

Expected: FastMCP boots and listens on port 8000.

- [ ] **Step 5: Hit it from a second terminal with a basic MCP client**

Use the FastMCP CLI's inspector or `mcp` CLI:

```bash
uv run fastmcp inspect http://localhost:8000
```

Verify the 5 tools (`meals`, `workouts`, `weights`, `get_summary`, `get_history`) show up with their schemas. Try `meals` with `{"op": "log", "description": "test", "kcal": 100, "source": "exact"}`. Confirm the row appears in Neon (`select * from meals;`).

- [ ] **Step 6: Document the smoke flow in README**

Replace `README.md` contents with:

````markdown
# Calorie Coach MCP

Personal calorie & sport tracker exposed as an MCP server. Designed to be paired with a Claude
project whose system prompt holds your goals (target kcal, current weight, etc.) — the MCP
itself is a pure event journal.

## Local dev

```bash
uv sync --extra dev
cp .env.example .env  # fill in DATABASE_URL and MCP_BEARER_TOKEN
psql "$DATABASE_URL" -f init_db.sql
uv run python main.py
```

## Tests

```bash
uv run pytest
```

## Deployment

Deployed to Railway. Environment variables: `DATABASE_URL`, `MCP_BEARER_TOKEN`, `PORT`
(Railway injects `PORT` automatically).
````

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: local smoke instructions"
```

---

## Task 13: Railway deployment

**Files:**
- Create: `Procfile`

- [ ] **Step 1: Create `Procfile`**

```
web: uv run python main.py
```

- [ ] **Step 2: Verify Railway will pick up Python via `pyproject.toml`**

Railway's Nixpacks Python detector reads `pyproject.toml`. Confirm `requires-python = ">=3.13"` is set (it is, from Task 1).

- [ ] **Step 3: Push to a GitHub repo**

```bash
gh repo create calorie-coach-mcp --private --source=. --push
```

- [ ] **Step 4: Create Railway project linked to the repo**

In the Railway dashboard: **New Project → Deploy from GitHub Repo → select repo**.

- [ ] **Step 5: Set env vars in Railway**

Add: `DATABASE_URL` (the Neon pooled URL), `MCP_BEARER_TOKEN` (the same long random string from local — or a different one; you'll need to give Claude the prod one).

- [ ] **Step 6: Trigger a deploy and tail logs**

In Railway: deploy. Watch logs until you see FastMCP listening on the assigned port.

- [ ] **Step 7: Smoke-test the deployed URL**

Railway gives you a `*.up.railway.app` URL. Hit it with the inspector:

```bash
uv run fastmcp inspect https://<your-app>.up.railway.app
```

Expected: 5 tools listed.

- [ ] **Step 8: Connect Claude to the remote MCP**

In Claude Desktop's settings → MCP servers, add a remote server entry pointing at `https://<your-app>.up.railway.app` with the `Authorization: Bearer <MCP_BEARER_TOKEN>` header. Restart Claude Desktop.

- [ ] **Step 9: End-to-end conversation test**

In Claude: "log a coffee with milk, ~80 kcal, exact". Then "what's my summary today?". Verify Claude calls the right tools and gets coherent responses.

- [ ] **Step 10: Commit**

```bash
git add Procfile
git commit -m "chore: Railway Procfile"
```

---

## Self-review checklist (already executed by the planner)

- ✓ Spec coverage: §1 goal — all tools cover it. §2 scope — Tasks 6/7/8 implement meals/workouts/weights with the exact fields. §3 architecture — Tasks 1/4/11/13. §4 schema — Task 4 (`init_db.sql` + SQLModel). §5 tools — Tasks 6/7/8/9/11. §6 resolved decisions — distributed across Tasks 4/9/10/11/13. §7 open items — driver chosen as `psycopg` v3 (Task 1).
- ✓ No placeholders in concrete code blocks. Two explicit caveats (FastMCP API drift in Task 11 step 4; SQLAlchemy URL prefix in Task 4) point the engineer at the docs rather than guess.
- ✓ Type/name consistency: `handle_meals`/`handle_workouts`/`handle_weights` everywhere, `get_summary`/`get_history` everywhere, `MealsPayload`/`WorkoutsPayload`/`WeightsPayload`, `paris_day_bounds`, `parse_iso_or_date`, `check_bearer`. `from_` aliased to `from` in JSON. `kcal_burned` consistent.

---

**Plan complete and saved to [`docs/superpowers/plans/2026-05-10-calorie-coach-mcp.md`](.). Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
