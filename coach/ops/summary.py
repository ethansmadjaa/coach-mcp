from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import Any
from sqlmodel import Session, col, select
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
        select(Weight)
        .where(Weight.measured_at >= start, Weight.measured_at < end)
        .order_by(col(Weight.measured_at).desc())
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
