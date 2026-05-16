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
