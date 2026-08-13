from datetime import date


SEASON_LABELS = {
    "spring": "pomlad",
    "summer": "poletje",
    "autumn": "jesen",
    "winter": "zima",
}


def season_for_date(value: date) -> str:
    if value.month in (3, 4, 5):
        return "spring"
    if value.month in (6, 7, 8):
        return "summer"
    if value.month in (9, 10, 11):
        return "autumn"
    return "winter"


def estimated_seasonal_days(days_to_harvest: int) -> dict[str, int]:
    """Create conservative seasonal planning estimates from an older single value."""
    return {
        "spring": days_to_harvest,
        "summer": max(1, round(days_to_harvest * 0.9)),
        "autumn": max(1, round(days_to_harvest * 1.15)),
        "winter": max(1, round(days_to_harvest * 1.45)),
    }


def maturity_days_for_date(variety: object, value: date) -> int:
    season = season_for_date(value)
    seasonal_value = getattr(variety, f"days_{season}", None)
    if seasonal_value is not None:
        return int(seasonal_value)
    return estimated_seasonal_days(int(getattr(variety, "days_to_harvest")))[season]


def maturity_details(variety: object, value: date) -> dict[str, int | str]:
    season = season_for_date(value)
    return {
        "maturity_season": season,
        "maturity_season_label": SEASON_LABELS[season],
        "maturity_days": maturity_days_for_date(variety, value),
    }
