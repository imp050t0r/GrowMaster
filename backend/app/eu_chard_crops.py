"""EU-first Swiss chard / blitva crop profiles for the standalone Plant DB."""

VOLTZ_SWISS_CHARD = "https://be.voltz-maraichage.com/sites/default/files/2023-10/LGDM_Bio_2024_Ipad_compressed_0.pdf"
VOLTZ_BABY_LEAF = "https://es.es.voltz-maraichage.com/sites/default/files/2024-11/lgdm_es_bio_25_web.pdf"

_COMMON = {
    "english_name": "Swiss chard",
    "botanical_name": "Beta vulgaris var. cicla",
    "family": "Amaranthaceae",
    "category": "Listnata",
    "planting_method": "direct",
    "heat_tolerance": "srednja",
    "cold_tolerance": "visoka",
    "cultivation_methods": "direct,transplant",
    "nursery_days": 42,
    "direct_sow_extra_days": None,
    "days_green_harvest": None,
    "harvest_interval_days": None,
    "harvest_duration_days": None,
}


def _standard(name, traits, *, source_url=VOLTZ_SWISS_CHARD, seed_forms="navadno ali ekološko seme"):
    return {
        **_COMMON,
        "crop": "Blitva",
        "name": name,
        "days": 55,
        "source_name": "Voltz Maraîchage EU",
        "source_url": source_url,
        "seed_forms": seed_forms,
        "traits": traits,
        "slovenia_note": "EU-first sorta blitve za sveži trg; primerna za spomladansko, poletno in jesensko pridelavo v Sloveniji.",
        "days_baby": 30,
        "seed_rate_g_m2": 0.30,
        "seed_spacing_cm": 30.0,
        "row_spacing_cm": 65.0,
        "outdoor_months": "3,4,5,6,7,8,9",
        "protected_months": "2,3,4,9,10,11",
        "planting_calendar_note": "Voltz navaja setev marec–september; kalitev približno 6–14 dni. Za standardno pridelavo ciljaj 40.000–50.000 rastlin/ha.",
        "succession_interval_days": 21,
        "calendar_source_url": source_url,
        "harvest_methods": "outer_leaves,full_size,cut_and_regrow",
        "days_outer_leaf": 50,
        "regrowth_interval_min_days": 10,
        "regrowth_interval_max_days": 18,
        "max_regrowth_cuts": 5,
        "harvest_profile_note": "Obiraj zunanje liste in ohrani srček; pri ugodnih razmerah je možnih več rezov.",
        "harvest_source_url": source_url,
    }


def _baby(name, traits, *, source_url=VOLTZ_BABY_LEAF):
    return {
        **_COMMON,
        "crop": "Baby leaf blitva",
        "name": name,
        "days": 30,
        "source_name": "Voltz Maraîchage EU",
        "source_url": source_url,
        "seed_forms": "navadno ali ekološko seme",
        "traits": traits,
        "slovenia_note": "EU profesionalni baby-leaf tip. Gosta direktna setev za mlade liste in večkratno rezanje.",
        "days_baby": 30,
        "seed_rate_g_m2": None,
        "seed_spacing_cm": None,
        "row_spacing_cm": None,
        "outdoor_months": "3,4,5,6,7,8,9,10",
        "protected_months": "2,3,4,5,9,10,11",
        "planting_calendar_note": "Voltz ga vodi v programu Baby Leaf; prilagodi termin setve zahtevani velikosti lista in temperaturi.",
        "succession_interval_days": 14,
        "calendar_source_url": source_url,
        "harvest_methods": "baby_leaf,cut_and_regrow",
        "days_outer_leaf": None,
        "regrowth_interval_min_days": 10,
        "regrowth_interval_max_days": 16,
        "max_regrowth_cuts": 4,
        "days_green_harvest": 30,
        "harvest_profile_note": "Reži mlade liste nad rastnim središčem; pri enakomerni rasti omogoča več zaporednih rezov.",
        "harvest_source_url": source_url,
    }


EU_CHARD_CROPS = [
    _standard("Verte à Carde Blanche 3 Race B", "Temno zeleni mehurjasti listi in široki beli peclji; standardna profesionalna tržna sorta."),
    _standard("Jessica", "Kompaktna pokončna Barese blitva s temno zelenimi gladkimi listi in belimi peclji; hitra rast, dobra odpornost na mraz."),
    _standard("Bright Lights", "Pisani peclji v beli, rožnati, rdeči, zeleni in rumeni barvi; zelo primerna za barvit sveži trg."),
    _standard("Bright Yellow", "Rumeni peclji in rumene listne žile; izrazit barvni tip."),
    _standard("Rhubarb Chard Rubis", "Širši listi in močno rdeče obarvani peclji; primerna tudi za barvni baby-leaf program."),
    _standard("Galaxy F1", "Rdečepecljati hibrid z visoko izenačenostjo, dobro toleranco na mraz in visokim pridelkom v hladnejšem delu sezone.", seed_forms="netretirano seme"),
    _baby("Verte à Couper (Bette à Tondre)", "Zelena blitva s tankimi peclji, posebej namenjena večkratnemu rezanju; Voltz jo vodi v programu Baby Leaf."),
    _baby("Barby", "Izenačena rast za baby leaf, močno rdeče obarvane žile in listi ter dobra obstojnost po rezi."),
    _baby("Rhubarb Chard Rubis", "Rdeči peclji in široki listi; baby-leaf različica za barvni kontrast v mešanicah."),
]
