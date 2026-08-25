"""Indian and Nepalese crops requested for the GrowMaster Plant DB."""

TNAU_GARDEN = "https://agritech.tnau.ac.in/horticulture/horti_Landscaping_types%20of%20garden.html"
TNAU_FENUGREEK = "https://agritech.tnau.ac.in/horticulture/horti_spice%20crops_fenugreek.html"
TNAU_GOURDS = "https://www.agritech.tnau.ac.in/farm_innovations/farm_innovations_pandal_veg_e.html"
TNAU_OKRA = "https://agritech.tnau.ac.in/org_farm/orgfarm_bhendi_cultivation.html"
TARO_SOURCE = "https://agritech.tnau.ac.in/org_farm/pdf/Horticulture5_231009_094153.pdf"
ICAR_TORIA = "https://www.icar.gov.in/sites/default/files/2022-09/Rabi-Agro-Advisory-2021-22_0.pdf"
ICAR_TS38 = "https://icar.gov.in/en/field-day-toria-variety-ts-38-organized"
TNAU_OYSTER = "https://agritech.tnau.ac.in/pdf/HORTICULTURE.pdf"


def crop(
    crop_name, name, family, category, days, source, *, method="direct",
    outdoor="5,6", protected="4,5,6", heat="visoka", cold="nizka",
    spacing=30.0, rows=45.0, seed_rate=None, traits, note,
    nursery=None, harvest="full_size", interval=None, duration=None,
):
    return {
        "crop": crop_name, "name": name, "family": family, "category": category,
        "days": days, "source_name": "TNAU/ICAR agronomska priporočila",
        "source_url": source, "seed_forms": "navadno seme" if method != "vegetative" else "sadni gomolj",
        "traits": traits, "slovenia_note": note, "days_baby": 25 if harvest == "baby_leaf" else None,
        "seed_rate_g_m2": seed_rate, "seed_spacing_cm": spacing, "row_spacing_cm": rows,
        "planting_method": method, "outdoor_months": outdoor, "protected_months": protected,
        "heat_tolerance": heat, "cold_tolerance": cold,
        "planting_calendar_note": note, "succession_interval_days": 14 if harvest in {"leaf", "baby_leaf"} else None,
        "calendar_source_url": source, "cultivation_methods": method,
        "harvest_methods": harvest, "nursery_days": nursery, "direct_sow_extra_days": None,
        "days_outer_leaf": days if harvest == "leaf" else None,
        "regrowth_interval_min_days": 10 if harvest == "leaf" else None,
        "regrowth_interval_max_days": 18 if harvest == "leaf" else None,
        "max_regrowth_cuts": 3 if harvest == "leaf" else None,
        "days_green_harvest": days if harvest in {"green_fruit", "pods"} else None,
        "harvest_interval_days": interval, "harvest_duration_days": duration,
        "harvest_profile_note": note, "harvest_source_url": source,
    }


WARM_NOTE = "Toploljubna južnoazijska kultura; v Sloveniji jo sej oziroma presadi po slani, za zanesljiv pridelek pa uporabi tunel."
COOL_NOTE = "Južnoazijski hladnosezonski tip; v Sloveniji je najzanesljivejši spomladi in jeseni."

SOUTH_ASIAN_REQUESTED_CROPS = [
    crop("Bamija", "Arka Anamika", "Malvaceae", "Indijska", 55, TNAU_OKRA,
         spacing=30, rows=45, traits="Indijska neolesenela okra/bhindi z dolgimi zelenimi stroki.", note=WARM_NOTE,
         harvest="pods", interval=3, duration=60),
    crop("Azijska gorčica", "Pusa Sag-1", "Brassicaceae", "Indijska", 40, TNAU_GARDEN,
         outdoor="3,4,8,9,10", protected="2,3,4,9,10,11", heat="srednja", cold="visoka",
         spacing=10, rows=20, seed_rate=0.6, traits="Listna gorčica za saag in mlade liste.", note=COOL_NOTE, harvest="leaf"),
    crop("Palak", "Pusa All Green", "Amaranthaceae", "Indijska", 40, TNAU_GARDEN,
         outdoor="3,4,8,9,10", protected="2,3,4,9,10,11", heat="srednja", cold="visoka",
         spacing=7.5, rows=20, seed_rate=3.0, traits="Indijska gladkolistna špinača/palak za več rezov.", note=COOL_NOTE, harvest="leaf"),
    crop("Methi", "Indian Fenugreek", "Fabaceae", "Indijska", 30, TNAU_FENUGREEK,
         outdoor="3,4,8,9", protected="2,3,4,9,10", heat="srednja", cold="srednja",
         spacing=5, rows=20, seed_rate=1.2, traits="Fenugreek/methi za list in mlade poganjke.", note=COOL_NOTE, harvest="leaf"),
    crop("Buča", "Arka Chandan", "Cucurbitaceae", "Indijska", 100, TNAU_GARDEN,
         method="transplant", spacing=90, rows=120, traits="Indijski tip buče za zrele plodove.", note=WARM_NOTE, nursery=24),
    crop("Kumara", "Pusa Uday", "Cucurbitaceae", "Indijska", 55, TNAU_GARDEN,
         method="transplant", spacing=35, rows=80, traits="Zgodnja indijska kumara za sveže zelene plodove.", note=WARM_NOTE,
         nursery=21, harvest="green_fruit", interval=3, duration=45),
    crop("Toria", "TS-38", "Brassicaceae", "Indijska", 125, ICAR_TS38,
         outdoor="3,4,8,9", protected="2,3,4,9,10", heat="srednja", cold="visoka",
         spacing=10, rows=30, seed_rate=0.35, traits="Zgodnja oljna ogrščica/toria z 40–45 % olja.", note=COOL_NOTE, harvest="seed"),
    crop("Toria", "T-9", "Brassicaceae", "Indijska", 95, ICAR_TORIA,
         outdoor="3,4,8,9", protected="2,3,4,9,10", heat="srednja", cold="visoka",
         spacing=10, rows=30, seed_rate=0.35, traits="Kratkosezonska toria za zrnje in olje.", note=COOL_NOTE, harvest="seed"),
    crop("Karela", "Small Indian", "Cucurbitaceae", "Indijska", 55, TNAU_GOURDS,
         method="transplant", spacing=75, rows=150, traits="Majhnoplodni, izrazito grenak tip karele.", note=WARM_NOTE,
         nursery=24, harvest="green_fruit", interval=3, duration=60),
    crop("Karela", "Large Indian", "Cucurbitaceae", "Indijska", 60, TNAU_GOURDS,
         method="transplant", spacing=90, rows=150, traits="Velikoplodni indijski tip grenke kumare.", note=WARM_NOTE,
         nursery=24, harvest="green_fruit", interval=3, duration=60),
    crop("Grah", "Arkel", "Fabaceae", "Indijska", 60, TNAU_GARDEN,
         outdoor="2,3,4,8,9", protected="2,3,4,9,10", heat="nizka", cold="visoka",
         spacing=5, rows=30, traits="Zgodnji indijski vrtni grah za sveže stroke.", note=COOL_NOTE,
         harvest="pods", interval=4, duration=21),
    crop("Redkvica", "Pusa Chetki", "Brassicaceae", "Indijska", 45, TNAU_GARDEN,
         outdoor="3,4,5,8,9", protected="2,3,4,9,10", heat="visoka", cold="srednja",
         spacing=10, rows=15, seed_rate=1.0, traits="Toplotno tolerantna indijska bela redkev.", note=COOL_NOTE),
    crop("Fižol", "Arka Komal", "Fabaceae", "Indijska", 55, TNAU_GARDEN,
         spacing=15, rows=45, traits="Indijski nizki stročji fižol za zelene stroke.", note=WARM_NOTE,
         harvest="pods", interval=4, duration=30),
    crop("Lauki", "Pusa Naveen", "Cucurbitaceae", "Indijska", 65, TNAU_GOURDS,
         method="transplant", spacing=90, rows=150, traits="Bottle gourd/lauki z dolgimi svetlo zelenimi plodovi.", note=WARM_NOTE,
         nursery=24, harvest="green_fruit", interval=4, duration=60),
    crop("Taro", "Sree Rashmi", "Araceae", "Indijska", 240, TARO_SOURCE,
         method="vegetative", outdoor="5,6", protected="4,5", spacing=45, rows=60,
         traits="Taro/colocasia za užitne gomolje; razmnožuje se s stranskimi gomolji.", note=WARM_NOTE, harvest="tubers"),
    crop("Koriander", "CO-4", "Apiaceae", "Indijska", 40, TNAU_FENUGREEK,
         outdoor="3,4,5,8,9", protected="2,3,4,9,10", heat="srednja", cold="srednja",
         spacing=5, rows=20, seed_rate=0.6, traits="Koriander/dhania za list in seme.", note=COOL_NOTE, harvest="leaf"),
    crop("Chichinda", "CO-2", "Cucurbitaceae", "Indijska", 65, TNAU_GOURDS,
         method="transplant", spacing=100, rows=180, traits="Snake gourd/chichinda za dolge mlade zelene plodove na opori.", note=WARM_NOTE,
         nursery=24, harvest="green_fruit", interval=3, duration=60),
    crop("Gobe", "Ostrigar", "Pleurotaceae", "Gobe", 28, TNAU_OYSTER,
         method="indoor_substrate", outdoor="", protected="1,2,3,4,5,6,7,8,9,10,11,12",
         heat="srednja", cold="srednja", spacing=None, rows=None,
         traits="Ostrigar za nadzorovano pridelavo na pasteriziranem substratu.",
         note="Ni poljščina: goji se v čistem, vlažnem in prezračevanem prostoru na inokuliranem substratu.",
         harvest="flushes", interval=7, duration=45),
]
