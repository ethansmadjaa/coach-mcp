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
        if isinstance(f, datetime):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Workout.done_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if isinstance(t, datetime):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Workout.done_at < end)
    return [_serialize(w) for w in session.exec(stmt).all()]
