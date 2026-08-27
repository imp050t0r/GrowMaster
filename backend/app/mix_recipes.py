"""Structured GrowMaster baby-leaf recipes and bed seed calculations.

Percentages are harvest/product target shares. Components marked separate_then_mix
are sown as separate crop blocks and combined after harvest. Seed requirements
are calculated from each component's own seed rate, never from one blended rate.
"""

BABY_LEAF_MIX_RECIPES = [
    {
        "id": "asian_balanced_v1",
        "name": "Asian Mix",
        "category": "Baby leaf mešanica",
        "strategy": "separate_then_mix",
        "components": [
            {"crop": "Mizuna", "share_pct": 30},
            {"crop": "Tatsoi", "share_pct": 25},
            {"crop": "Pak choi", "share_pct": 20},
            {"crop": "Rdeča gorčica", "share_pct": 15},
            {"crop": "Baby leaf regrat", "share_pct": 10},
        ],
        "note": "Deleži so ciljna sestava končnega pridelka. Količino semena računaj po setveni normi vsake komponente.",
    },
    {
        "id": "italian_balanced_v1",
        "name": "Italian Baby Leaf Mix",
        "category": "Baby leaf mešanica",
        "strategy": "separate_then_mix",
        "components": [
            {"crop": "Rukola", "share_pct": 35},
            {"crop": "Solata hrastov list rdeč", "share_pct": 20},
            {"crop": "Solata hrastov list zelen", "share_pct": 20},
            {"crop": "Radič", "share_pct": 15},
            {"crop": "Baby leaf regrat", "share_pct": 10},
        ],
        "note": "Komponente sej ločeno in jih združi po rezi; tako uskladiš različne hitrosti rasti in termin žetve.",
    },
]


def validate_mix_recipe(recipe):
    return bool(recipe.get("components")) and sum(
        component["share_pct"] for component in recipe["components"]
    ) == 100


def get_mix_recipe(recipe_id: str):
    for recipe in BABY_LEAF_MIX_RECIPES:
        if recipe["id"] == recipe_id:
            return recipe
    raise KeyError(recipe_id)


def calculate_mix_seed_requirements(
    recipe_id: str,
    width_m: float,
    length_m: float,
    seed_rates_g_m2: dict[str, float],
    reserve_pct: float = 5.0,
):
    """Calculate component block area and grams of seed for one bed.

    share_pct allocates the bed/product target between separately sown components.
    Each component uses its own g/m2 rate. A small configurable reserve is then
    added for calibration, headlands and normal sowing loss.
    """
    if width_m <= 0 or length_m <= 0:
        raise ValueError("Širina in dolžina gredice morata biti večji od 0.")
    if reserve_pct < 0 or reserve_pct > 100:
        raise ValueError("Rezerva mora biti med 0 in 100 %.")
    recipe = get_mix_recipe(recipe_id)
    if not validate_mix_recipe(recipe):
        raise ValueError("Receptura mešanice nima pravilnih 100 % deležev.")
    bed_area_m2 = width_m * length_m
    components = []
    missing_rates = []
    total_seed_g = 0.0
    for component in recipe["components"]:
        crop = component["crop"]
        share = component["share_pct"] / 100.0
        component_area = bed_area_m2 * share
        rate = seed_rates_g_m2.get(crop)
        required_g = None
        if rate is None or rate <= 0:
            missing_rates.append(crop)
        else:
            required_g = component_area * rate * (1.0 + reserve_pct / 100.0)
            total_seed_g += required_g
        components.append({
            **component,
            "area_m2": round(component_area, 3),
            "seed_rate_g_m2": rate,
            "required_seed_g": round(required_g, 2) if required_g is not None else None,
        })
    return {
        "recipe_id": recipe["id"],
        "name": recipe["name"],
        "strategy": recipe["strategy"],
        "bed_width_m": width_m,
        "bed_length_m": length_m,
        "bed_area_m2": round(bed_area_m2, 2),
        "reserve_pct": reserve_pct,
        "components": components,
        "total_seed_g": round(total_seed_g, 2),
        "missing_seed_rates": missing_rates,
        "ready": not missing_rates,
    }
