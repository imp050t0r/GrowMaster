"""Structured GrowMaster baby-leaf recipes.

Percentages are harvest/product target shares. Components marked separate_then_mix
should be sown as separate crop blocks and combined after harvest so different
emergence and growth rates can be managed independently.
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
        "note": "Deleži so ciljna sestava končnega pridelka. GrowMaster mora količino semena računati po setveni normi vsake komponente, ne kot enotno g/m² mešanice.",
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
        "note": "Komponente sej ločeno in jih združi po rezi; tako je mogoče uskladiti različne hitrosti rasti in termin žetve.",
    },
]


def validate_mix_recipe(recipe):
    """Return True only for recipes whose component shares total exactly 100%."""
    return sum(component["share_pct"] for component in recipe.get("components", [])) == 100
