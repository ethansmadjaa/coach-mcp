from datetime import datetime, timezone
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
        if isinstance(f, datetime):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Meal.eaten_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if isinstance(t, datetime):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Meal.eaten_at < end)
    return [_serialize(m) for m in session.exec(stmt).all()]
