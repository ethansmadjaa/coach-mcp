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
        if isinstance(f, datetime):
            start = f.astimezone(timezone.utc)
        else:
            start, _ = paris_day_bounds(f)
        stmt = stmt.where(Weight.measured_at >= start)
    if p.to is not None:
        t = parse_iso_or_date(p.to)
        if isinstance(t, datetime):
            end = t.astimezone(timezone.utc)
        else:
            _, end = paris_day_bounds(t)
        stmt = stmt.where(Weight.measured_at < end)
    return [_serialize(w) for w in session.exec(stmt).all()]
