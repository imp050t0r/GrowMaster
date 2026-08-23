from datetime import date


MIXTURE_ROTATION_FAMILIES = {
    "Klasična solatna mešanica": {
        "Asteraceae",
        "Amaranthaceae",
        "Brassicaceae",
    },
    "Azijska mešanica": {"Brassicaceae"},
    "Pikantna mešanica": {"Brassicaceae"},
}

WARM_SEASON_CROPS = {
    "Paradižnik",
    "Paprika",
    "Feferon",
    "Jajčevec",
    "Kumara",
    "Bučka",
    "Buča",
    "Fižol",
    "Edamame",
    "Bamija",
    "Karela",
    "Lauki",
    "Rebrasta bučka",
    "Gobasta bučka",
    "Tinda",
    "Voščena buča",
    "Indijski jajčevec",
    "Indijski čili",
    "Nepalski zeleni čili",
    "Malabarska špinača",
    "Listni amarant",
    "Guar",
}

WINTER_FRIENDLY_CROPS = {
    "Špinača",
    "Motovilec",
    "Por",
    "Česen",
    "Ohrovt",
    "Radič",
    "Endivija",
}


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

    repeated_at: int | None = None
    for index, previous_families in enumerate(recent_family_sets[:4]):
        if candidate_families & previous_families:
            repeated_at = index
            break
    if repeated_at is None:
        score += 25
        if recent_family_sets:
            reasons.append("Rastlinske družine ni v zadnjih štirih ciklih gredice.")
        else:
            reasons.append("Za gredico še ni zabeležene kolobarske omejitve.")
    elif repeated_at == 0:
        score -= 65
        warnings.append("Ista rastlinska družina je bila na gredici v zadnjem ciklu.")
    elif repeated_at == 1:
        score -= 35
        warnings.append("Rastlinska družina se je pojavila pred dvema cikloma.")
    else:
        score -= 15
        warnings.append("Rastlinska družina se je pojavila v zadnjih štirih ciklih.")

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
