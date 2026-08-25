from datetime import date
import json
from pathlib import Path


_DATA_FILE = Path(__file__).with_name("data") / "rotation_rules.json"


def _load_rules() -> dict:
    with _DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_RULES = _load_rules()
MIXTURE_ROTATION_FAMILIES = {
    name: set(families)
    for name, families in _RULES["mixture_rotation_families"].items()
}
WARM_SEASON_CROPS = set(_RULES["warm_season_crops"])
WINTER_FRIENDLY_CROPS = set(_RULES["winter_friendly_crops"])
ROTATION_RULES = _RULES["rotation"]


def rotation_families(
    crop_name: str,
    crop_family: str,
    variety_name: str | None = None,
) -> set[str]:
    if crop_name == "Baby leaf mešanica" and variety_name:
        return MIXTURE_ROTATION_FAMILIES.get(variety_name, {crop_family})
    return {crop_family}


def seasonal_assessment(
    crop_name: str,
    crop_category: str,
    sowing_date: date,
) -> tuple[int, str, str | None]:
    month = sowing_date.month
    if crop_name in WARM_SEASON_CROPS:
        if month in (3, 4, 5, 6):
            return 15, "Termin je primeren za toploljubno kulturo.", None
        if month == 7:
            return 0, "Termin je pozen za toploljubno kulturo.", (
                "Preveri dolžino preostale rastne sezone ali uporabi zaščiten prostor."
            )
        return -60, "Termin ni običajen za toploljubno kulturo.", (
            "Pred setvijo preveri temperaturo in možnost zaščitene pridelave."
        )
    if crop_category == "Baby leaf":
        if month in (3, 4, 5, 8, 9, 10):
            return 15, "Termin je zelo primeren za baby-leaf pridelavo.", None
        return 6, "Baby leaf omogoča kratek in prilagodljiv rastni cikel.", None
    if month in (12, 1, 2):
        if crop_name in WINTER_FRIENDLY_CROPS:
            return 10, "Kultura je primerna za hladnejši del leta.", None
        return -25, "Zimski termin zahteva dodatno presojo.", (
            "Upoštevaj nizke temperature, svetlobo in morebitno zaščito posevka."
        )
    return 5, "Termin je sezonsko sprejemljiv.", None


def score_candidate(
    candidate_families: set[str],
    recent_family_sets: list[set[str]],
    maturity_days: int,
    seasonal_score: int,
    has_plan_conflict: bool,
    previous_yield_per_m2: float | None,
) -> dict:
    score = 70 + seasonal_score
    reasons: list[str] = []
    warnings: list[str] = []

    history_cycles = int(ROTATION_RULES.get("history_cycles", 4))
    penalties = ROTATION_RULES.get("same_family_penalties", {})
    different_family_bonus = int(ROTATION_RULES.get("different_family_bonus", 25))

    repeated_at: int | None = None
    for index, previous_families in enumerate(recent_family_sets[:history_cycles]):
        if candidate_families & previous_families:
            repeated_at = index
            break
    if repeated_at is None:
        score += different_family_bonus
        if recent_family_sets:
            reasons.append(
                f"Rastlinske družine ni v zadnjih {history_cycles} ciklih gredice."
            )
        else:
            reasons.append("Za gredico še ni zabeležene kolobarske omejitve.")
    elif repeated_at == 0:
        score += int(penalties.get("previous_cycle", -65))
        warnings.append("Ista rastlinska družina je bila na gredici v zadnjem ciklu.")
    elif repeated_at == 1:
        score += int(penalties.get("two_cycles_ago", -35))
        warnings.append("Rastlinska družina se je pojavila pred dvema cikloma.")
    else:
        score += int(penalties.get("within_history", -15))
        warnings.append(
            f"Rastlinska družina se je pojavila v zadnjih {history_cycles} ciklih."
        )

    if has_plan_conflict:
        score -= 70
        warnings.append("Termin se prekriva z že načrtovano zasaditvijo gredice.")
    else:
        reasons.append("V terminu ni prekrivanja z načrtovanimi zasaditvami.")

    if maturity_days <= 45:
        score += 12
        reasons.append(f"Kratek predvideni cikel: približno {maturity_days} dni.")
    elif maturity_days <= 90:
        score += 7
        reasons.append(f"Predvideni cikel je približno {maturity_days} dni.")
    elif maturity_days > 180:
        score -= 8
        warnings.append(f"Predvideni cikel je dolg: približno {maturity_days} dni.")

    if previous_yield_per_m2 is not None and previous_yield_per_m2 > 0:
        score += min(12, round(previous_yield_per_m2))
        reasons.append(
            "Kultura ima na tej gredici zabeležen pridelek "
            f"{previous_yield_per_m2:.2f} kg/m²."
        )

    if score >= 100 and not warnings:
        rating = "recommended"
        rating_label = "Zelo primerno"
    elif score >= 70:
        rating = "acceptable"
        rating_label = "Primerno"
    else:
        rating = "caution"
        rating_label = "Previdno"
    return {
        "score": max(0, score),
        "rating": rating,
        "rating_label": rating_label,
        "reasons": reasons,
        "warnings": warnings,
    }
