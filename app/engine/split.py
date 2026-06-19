"""
Maps training_days_per_week to a weekly split layout.
Returns a list of day-type strings in Mon–Sun order.
"rest" days are included so the list is always length 7.
"""

# Pure PPL: 3 or 6 days. 4-5 days use hybrid patterns.
_SPLITS: dict[int, list[str]] = {
    3: ["push", "rest", "pull", "rest", "legs", "rest", "rest"],
    4: ["push", "pull", "rest", "legs", "push", "rest", "rest"],
    5: ["push", "pull", "legs", "rest", "push", "pull", "rest"],
    6: ["push", "pull", "legs", "push", "pull", "legs", "rest"],
}


def week_split(training_days: int) -> list[str]:
    if training_days not in _SPLITS:
        raise ValueError(f"Unsupported training_days_per_week: {training_days}. Supported: {list(_SPLITS)}")
    return _SPLITS[training_days]


DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def labeled_split(training_days: int) -> list[dict]:
    """Returns [{"day_of_week": "monday", "type": "push"}, ...]"""
    types = week_split(training_days)
    return [{"day_of_week": day, "type": t} for day, t in zip(DAYS_OF_WEEK, types)]
