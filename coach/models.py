from datetime import datetime, timezone
from decimal import Decimal
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Meal(SQLModel, table=True):
    __tablename__ = "meals"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True)
    eaten_at: datetime
    description: str
    kcal: Decimal
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    source: str  # 'estimated' | 'exact' — validated at the payload layer
    created_at: datetime = Field(default_factory=_utcnow)


class Workout(SQLModel, table=True):
    __tablename__ = "workouts"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True)
    done_at: datetime
    type: str
    duration_min: int
    kcal_burned: Decimal
    source: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Weight(SQLModel, table=True):
    __tablename__ = "weights"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True)
    measured_at: datetime
    kg: Decimal
    created_at: datetime = Field(default_factory=_utcnow)
