"""
Suggests a good send time for a follow-up email.

Heuristic (backed by general email-open-rate research: Tue/Wed/Thu mid-morning
outperforms Monday-morning inbox floods and Friday-afternoon check-outs):
  - Skip weekends.
  - Prefer Tuesday, Wednesday, or Thursday.
  - Land between 9:30-10:30 local time (recruiter's likely timezone —
    we use the job's location if known, else the user's own timezone).
  - Respect a minimum number of days of silence before nudging:
      * post_application_checkin -> at least 6 days after applying
      * long_silence_nudge       -> at least 13 days after the last follow-up
      * post_interview_thanks    -> within the next business morning (fast)
"""
from datetime import datetime, timedelta
import zoneinfo


def _next_weekday_in(dt: datetime, target_weekdays: set[int]) -> datetime:
    while dt.weekday() not in target_weekdays:
        dt += timedelta(days=1)
    return dt


def suggest_send_time(template_key: str, reference_date: datetime, user_timezone: str = "Asia/Kolkata") -> datetime:
    try:
        tz = zoneinfo.ZoneInfo(user_timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    now_local = reference_date.astimezone(tz) if reference_date.tzinfo else reference_date.replace(tzinfo=tz)

    if template_key == "post_interview_thanks":
        # Next business morning, 9:00 local — thank-you notes should go out fast.
        candidate = now_local + timedelta(days=1)
        candidate = _next_weekday_in(candidate, {0, 1, 2, 3, 4})
        return candidate.replace(hour=9, minute=0, second=0, microsecond=0)

    min_gap_days = 6 if template_key == "post_application_checkin" else 13
    candidate = now_local + timedelta(days=min_gap_days)
    # Nudge onto Tue/Wed/Thu (1, 2, 3) for the best response odds.
    candidate = _next_weekday_in(candidate, {1, 2, 3})
    return candidate.replace(hour=9, minute=30, second=0, microsecond=0)
