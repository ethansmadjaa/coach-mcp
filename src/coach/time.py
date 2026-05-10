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
