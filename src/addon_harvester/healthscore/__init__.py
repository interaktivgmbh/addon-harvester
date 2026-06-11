"""Pure scoring helpers shared by :mod:`~addon_harvester.healthscore.healthscore`.

These are stateless table-lookup / date utilities; the scoring rubric they walk lives in
:mod:`~addon_harvester.healthscore.config`.
"""

from datetime import date, datetime, timezone
from typing import Optional

from .config import Buckets

__all__ = ['score_below', 'score_at_least', 'age_in_days']


def score_below(value: float, buckets: Buckets) -> int:
    """Points for the first tier whose upper bound ``value`` falls under; 0 if it exceeds them all."""
    for upper_bound, points in buckets:
        if value < upper_bound:
            return points

    return 0


def score_at_least(value: float, buckets: Buckets) -> int:
    """Points for the first tier whose lower bound ``value`` meets; 0 if it reaches none."""
    for lower_bound, points in buckets:
        if value >= lower_bound:
            return points

    return 0


def age_in_days(day: Optional[str]) -> Optional[int]:
    """Whole days between an ``YYYY-MM-DD`` date and today (UTC), or ``None`` if absent/malformed."""
    if not day:
        return None

    try:
        parsed = datetime.strptime(day, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

    today: date = datetime.now(timezone.utc).date()

    return (today - parsed).days
