"""Conservative date suggestions; an uploaded file's time is never a visit date."""

import re
from datetime import date


def parse_visit_date(value: str | None) -> date | None:
    if not value:
        return None
    matches = re.findall(
        r"(?<!\d)(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})(?=$|[^\d]|\d{2}[:：]\d{2})",
        value,
    )
    dates = set()
    for year, month, day in matches:
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            return None
    return dates.pop() if len(dates) == 1 else None


def suggest_visit_date(fields, *, confirmed_only=False):
    by_key = {f.key: f for f in fields}
    for key in ("visit_time", "report_date"):
        field = by_key.get(key)
        if field is None or (confirmed_only and field.review_status == "pending"):
            continue
        value = field.confirmed_value
        if value is None and not confirmed_only:
            if field.candidate_status == "conflict":
                return None
            value = field.candidate_value
        if value:
            # If a stated visit date is ambiguous, do not quietly use a report date.
            return parse_visit_date(value)
    return None
