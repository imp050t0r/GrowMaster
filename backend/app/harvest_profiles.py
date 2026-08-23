"""Cultivation and harvest profiles used by the Gredicnik planner."""


ENDIVE_GROWING_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/vegetables/chicory/"
    "chicory-endive-escarole-key-growing-information.html"
)
BABY_CHICORY_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/vegetables/baby-leaf/"
    "chicory-baby-leaf-key-growing-information.html"
)

HARVEST_PROFILE_FIELDS = (
    "cultivation_methods",
    "harvest_methods",
    "nursery_days",
    "direct_sow_extra_days",
    "days_outer_leaf",
    "regrowth_interval_min_days",
    "regrowth_interval_max_days",
    "max_regrowth_cuts",
    "harvest_profile_note",
    "harvest_source_url",
    "days_baby",
)


def profile(
    cultivation_methods: str,
    harvest_methods: str,
    *,
    nursery_days: int | None = None,
    direct_sow_extra_days: int | None = None,
    days_baby: int | None = None,
    days_outer_leaf: int | None = None,
    regrowth_min: int | None = None,
    regrowth_max: int | None = None,
    max_cuts: int | None = None,
    note: str | None = None,
    source: str | None = None,
) -> dict:
    return {
        "cultivation_methods": cultivation_methods,
        "harvest_methods": harvest_methods,
        "nursery_days": nursery_days,
        "direct_sow_extra_days": direct_sow_extra_days,
        "days_baby": days_baby,
        "days_outer_leaf": days_outer_leaf,
        "regrowth_interval_min_days": regrowth_min,
        "regrowth_interval_max_days": regrowth_max,
        "max_regrowth_cuts": max_cuts,
        "harvest_profile_note": note,
        "harvest_source_url": source,
    }


ENDIVE_VARIETY_PROFILES = {
    "dečja glava": profile(
        "direct,transplant",
        "full_size,baby_leaf,outer_leaves,cut_and_regrow",
        nursery_days=25,
        direct_sow_extra_days=18,
        days_baby=35,
        days_outer_leaf=65,
        regrowth_min=5,
        regrowth_max=14,
        max_cuts=3,
        note=(
            "Za polno glavo je najzanesljivejša vzgoja iz sadik. Za baby leaf "
            "sej neposredno; ponovni rez uspeva najbolje v hladnejšem delu sezone."
        ),
        source=ENDIVE_GROWING_SOURCE,
    ),
    "eskariol zelena": profile(
        "direct,transplant",
        "full_size,baby_leaf,outer_leaves,cut_and_regrow",
        nursery_days=25,
        direct_sow_extra_days=18,
        days_baby=35,
        days_outer_leaf=62,
        regrowth_min=5,
        regrowth_max=14,
        max_cuts=3,
        note=(
            "Širokolistni eskariol za polno glavo ali zunanje liste. Poletna "
            "setev zahteva hladna, stalno vlažna tla; jesenski termini so varnejši."
        ),
        source=ENDIVE_GROWING_SOURCE,
    ),
    "dalmatinska kopica": profile(
        "direct,transplant",
        "full_size,baby_leaf,outer_leaves,cut_and_regrow",
        nursery_days=25,
        direct_sow_extra_days=18,
        days_baby=35,
        days_outer_leaf=65,
        regrowth_min=5,
        regrowth_max=14,
        max_cuts=3,
        note=(
            "Tradicionalna širokolistna endivija za čvrsto glavo in jesensko "
            "spravilo; za prezimovanje potrebuje mile razmere ali zaščito."
        ),
        source=ENDIVE_GROWING_SOURCE,
    ),
}


def default_harvest_profile(
    crop_name: str,
    category: str,
    variety_name: str,
    planting_method: str | None,
    days_to_harvest: int,
    days_baby: int | None = None,
) -> dict:
    """Return a conservative profile without claiming unsupported capabilities."""
    name = crop_name.casefold()
    category_name = category.casefold()
    variety = variety_name.casefold()
    if name == "endivija":
        return ENDIVE_VARIETY_PROFILES.get(
            variety,
            profile(
                "direct,transplant",
                "full_size,baby_leaf,outer_leaves,cut_and_regrow",
                nursery_days=25,
                direct_sow_extra_days=18,
                days_baby=35,
                days_outer_leaf=max(25, days_to_harvest - 18),
                regrowth_min=5,
                regrowth_max=14,
                max_cuts=3,
                note=(
                    "Endivijo lahko vzgojiš iz sadik ali neposredno poseješ. "
                    "Baby leaf in ponovni rez sta najzanesljivejša v hladnem vremenu."
                ),
                source=BABY_CHICORY_SOURCE,
            ),
        )
    if name == "radič":
        return profile(
            "direct,transplant",
            "full_size,baby_leaf,outer_leaves,cut_and_regrow",
            nursery_days=28,
            direct_sow_extra_days=18,
            days_baby=days_baby or 35,
            days_outer_leaf=max(25, days_to_harvest - 15),
            regrowth_min=7,
            regrowth_max=14,
            max_cuts=3,
            note=(
                "Radič vodi ločeno od endivije; termin in obliko spravila prilagodi sorti."
            ),
            source=BABY_CHICORY_SOURCE,
        )
    if category_name == "baby leaf":
        return profile(
            "direct",
            "baby_leaf,cut_and_regrow",
            days_baby=days_baby or days_to_harvest,
            regrowth_min=7,
            regrowth_max=14,
            max_cuts=3,
            note=(
                "Gosta neposredna setev za mlade liste; režemo nad rastnim središčem."
            ),
            source=BABY_CHICORY_SOURCE if "radič" in name or "cikor" in name else None,
        )
    if days_baby:
        return profile(
            planting_method or "direct",
            "full_size,baby_leaf,cut_and_regrow",
            nursery_days=28 if planting_method == "transplant" else None,
            days_baby=days_baby,
            regrowth_min=7,
            regrowth_max=14,
            max_cuts=2,
            note="Sorta ima dobaviteljev podatek za mladi pridelek.",
        )
    return profile(
        planting_method or "direct",
        "full_size",
        nursery_days=28 if planting_method == "transplant" else None,
        note="Za to sorto je trenutno potrjen izračun polnega pridelka.",
    )
