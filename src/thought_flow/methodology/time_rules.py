"""Gate C time helpers — OpenAlex publication_date → ISO week; flag boundary weeks."""

from __future__ import annotations

from datetime import date, datetime

ANALYSIS_WINDOW_START = date(2022, 11, 30)


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    return date.fromisoformat(text)


def openalex_iso_week_id(publication_date: date | datetime | str) -> str:
    """Canonical OpenAlex week bucket from publication_date: YYYY-Www (ISO 8601)."""
    d = _as_date(publication_date)
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def iso_week_date_range(week_id: str) -> tuple[date, date]:
    """Inclusive Monday–Sunday range for an ISO week id YYYY-Www."""
    year_s, week_s = week_id.split("-W", 1)
    year = int(year_s)
    week = int(week_s)
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    return monday, sunday


def flag_boundary_week(
    week_id: str,
    *,
    window_start: date = ANALYSIS_WINDOW_START,
    window_end: date | None = None,
) -> bool:
    """
    True when the ISO week is not fully contained in [window_start, window_end].

    Boundary weeks are flagged — never padded or fabricated to invent missing days.
    If window_end is None, only the start boundary is considered.
    """
    monday, sunday = iso_week_date_range(week_id)
    if monday < window_start <= sunday:
        return True
    if window_end is not None and monday <= window_end < sunday:
        return True
    return False
