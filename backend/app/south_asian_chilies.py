"""Indian and Nepalese chillies commonly harvested as green fruit."""


IARI_JWALA_SOURCE = (
    "https://www.nahep.ig.iari.res.in/files/Publication/Others/TOEPProfit.pdf"
)
IARI_SADABAHAR_SOURCE = (
    "https://www.iari.res.in/files/Latest-News/PusaSadabahar_06102018.pdf"
)
NARC_PEPPER_TRIAL_SOURCE = (
    "https://narc.gov.np/wp-content/uploads/2024/01/07-Article.pdf"
)
NARC_LANDRACE_SOURCE = (
    "https://narc.gov.np/wp-content/uploads/2020/07/Article-02.pdf"
)
NARC_AKABARE_SOURCE = (
    "https://opac.narc.gov.np/opac_css/index.php?"
    "id=14686&lvl=notice_display"
)


def chili(
    crop: str,
    name: str,
    days: int,
    *,
    source_name: str,
    source_url: str,
    traits: str,
    slovenia_note: str,
    days_green_harvest: int,
    harvest_note: str,
    seed_forms: str = "navadno seme",
) -> dict:
    return {
        "crop": crop,
        "name": name,
        "family": "Solanaceae",
        "category": "Indijska" if crop == "Indijski čili" else "Azijska",
        "days": days,
        "source_name": source_name,
        "source_url": source_url,
        "seed_forms": seed_forms,
        "traits": traits,
        "slovenia_note": slovenia_note,
        "days_baby": None,
        "seed_rate_g_m2": None,
        "seed_spacing_cm": None,
        "row_spacing_cm": 45.0,
        "planting_method": "transplant",
        "outdoor_months": "5,6",
        "protected_months": "4,5,6",
        "heat_tolerance": "visoka",
        "cold_tolerance": "nizka",
        "planting_calendar_note": (
            "Sadike vzgoji na toplem in jih presadi šele po nevarnosti slane. "
            "Za daljše obiranje zelenih plodov je v Sloveniji prednost tunel."
        ),
        "succession_interval_days": None,
        "calendar_source_url": source_url,
        "cultivation_methods": "transplant",
        "harvest_methods": "green_fruit,full_size",
        "nursery_days": 56,
        "direct_sow_extra_days": None,
        "days_outer_leaf": None,
        "regrowth_interval_min_days": None,
        "regrowth_interval_max_days": None,
        "max_regrowth_cuts": None,
        "days_green_harvest": days_green_harvest,
        "harvest_interval_days": 7,
        "harvest_duration_days": 49,
        "harvest_profile_note": harvest_note,
        "harvest_source_url": source_url,
    }


SOUTH_ASIAN_CHILIES = [
    chili(
        "Indijski čili",
        "Arka Harita F1",
        125,
        source_name="ICAR-IIHR – uradni register sort",
        source_url="https://nhfqr.iihr.res.in/CHILLI-HYBRID-F1-ARKA-HARITA.html",
        traits=(
            "Uradni profesionalni F1 hibrid zelenega indijskega čilija ICAR-IIHR. "
            "GrowMaster ga vodi ločeno od odprto oprašenih sort Pusa Jwala in Pusa Sadabahar."
        ),
        slovenia_note=(
            "Vzgoji ga zelo zgodaj in presadi v topel tunel. Navedeni čas je konservativna "
            "načrtovalska ocena za Slovenijo; po prvem letu jo prilagodi dejanskemu pridelku."
        ),
        days_green_harvest=78,
        harvest_note=(
            "Za svežo prodajo obiraj čvrste zelene plodove; 78 dni po presajanju je začetna "
            "načrtovalska ocena, ne prepis uradne sortne navedbe."
        ),
        seed_forms="profesionalno F1 seme",
    ),
    chili(
        "Indijski čili",
        "Pusa Jwala",
        130,
        source_name="ICAR – Indian Agricultural Research Institute",
        source_url=IARI_JWALA_SOURCE,
        traits=(
            "Klasičen indijski zeleni čili: 9–10 cm dolgi, svetlo zeleni in "
            "zelo pekoči plodovi, ki ob zrelosti postanejo svetlo rdeči."
        ),
        slovenia_note=(
            "Zelo primeren za prodajo indijskim in nepalskim kupcem. Sej januarja "
            "ali februarja, maja presadi v tunel oziroma na najtoplejšo lego."
        ),
        days_green_harvest=80,
        harvest_note=(
            "Za svežo prodajo obiraj čvrste svetlo zelene plodove približno tedensko."
        ),
    ),
    chili(
        "Indijski čili",
        "Pusa Sadabahar",
        140,
        source_name="ICAR – Indian Agricultural Research Institute",
        source_url=IARI_SADABAHAR_SOURCE,
        traits=(
            "Zelo pekoči 6–8 cm dolgi plodovi v pokončnih šopih; zeleni plodovi "
            "ob polni zrelosti postanejo temno rdeči."
        ),
        slovenia_note=(
            "Zaščiten prostor podaljša obiranje. V našem podnebju jo vodi kot "
            "enoletnico in redno pobiraj mlade zelene plodove."
        ),
        days_green_harvest=78,
        harvest_note=(
            "Prvo zeleno obiranje je približno 75–80 dni po presajanju; nato obiraj tedensko."
        ),
    ),
    chili(
        "Nepalski zeleni čili",
        "Suryamukhi",
        105,
        source_name="Nepal Agricultural Research Council",
        source_url=NARC_PEPPER_TRIAL_SOURCE,
        traits=(
            "Kratki trikotni, živo zeleni plodovi in veliko število plodov na rastlino."
        ),
        slovenia_note=(
            "Primeren za topel tunel. V nepalskem poskusu na 1.275 m je prvi zeleni "
            "pridelek dosegel približno 83 dni po presajanju."
        ),
        days_green_harvest=83,
        harvest_note=(
            "Obiraj živo zelene plodove; redno pobiranje spodbuja nadaljnje nastavljanje."
        ),
    ),
    chili(
        "Nepalski zeleni čili",
        "Kantipure",
        95,
        source_name="Nepal Agricultural Research Council",
        source_url=NARC_PEPPER_TRIAL_SOURCE,
        traits=(
            "Zgodnejši nepalski tip s podolgovatimi zelenimi plodovi, dolgimi okoli 7 cm."
        ),
        slovenia_note=(
            "Zanimiv za zgodnejši pridelek; poskus je pokazal prvo zeleno obiranje "
            "približno 72 dni po presajanju. V vlažnem vremenu skrbno spremljaj bolezni."
        ),
        days_green_harvest=72,
        harvest_note=(
            "Za svežo prodajo poberi podolgovate plodove še zelene in čvrste."
        ),
    ),
    chili(
        "Nepalski zeleni čili",
        "Jire Khursani",
        110,
        source_name="Nepal Agricultural Research Council",
        source_url=NARC_LANDRACE_SOURCE,
        traits=(
            "Tradicionalni nepalski drobnoplodni čili z dolgo rodnostjo; uporablja "
            "se zelen ali popolnoma dozorel."
        ),
        slovenia_note=(
            "Nepalski vir izpostavlja dolgotrajno rodnost. Za slovensko sezono ga "
            "vzgoji zelo zgodaj in prednostno v tunelu."
        ),
        days_green_harvest=90,
        harvest_note=(
            "Čas prvega zelenega obiranja je konservativna načrtovalska ocena; "
            "po prvem letu jo prilagodi dejanskemu rezultatu na kmetiji."
        ),
    ),
    chili(
        "Nepalski zeleni čili",
        "Akabare Khursani",
        125,
        source_name="Nepal Agricultural Research Council",
        source_url=NARC_AKABARE_SOURCE,
        traits=(
            "Značilen okrogel nepalski čili z zelo visoko pekočnostjo in visoko tržno vrednostjo."
        ),
        slovenia_note=(
            "Zelene plodove lahko prodajaš sveže, značilno aromo in barvo pa razvijejo "
            "ob rdeči zrelosti. Zaradi dolge sezone je tunel skoraj nujen."
        ),
        days_green_harvest=95,
        harvest_note=(
            "Zelen pridelek obiraj čvrst; za tradicionalni rdeči Akabare del plodov "
            "pusti dozoreti. Čas je začetna načrtovalska ocena."
        ),
    ),
]
