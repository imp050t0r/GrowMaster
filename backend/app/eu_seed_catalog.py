"""EU-first professional seed catalogue for GrowMaster.

Default purchasing guidance follows: Slovenia -> EU -> wider Europe -> non-EU only
when a suitable European source is unavailable.  Existing user-entered varieties
are never deleted by this catalogue.
"""

from app.planting_calendar import CALENDAR_FIELDS, default_calendar_for_crop


def eu_variety(
    crop: str,
    family: str,
    name: str,
    days: int,
    source_name: str,
    source_url: str,
    traits: str,
    slovenia_note: str,
    *,
    category: str = "Domača",
    seed_forms: str = "navadno",
    days_baby: int | None = None,
    seed_rate_g_m2: float | None = None,
    seed_spacing_cm: float | None = None,
    row_spacing_cm: float | None = None,
) -> dict:
    item = {
        "crop": crop,
        "family": family,
        "category": category,
        "name": name,
        "days": days,
        "source_name": source_name,
        "source_url": source_url,
        "seed_forms": seed_forms,
        "traits": traits,
        "slovenia_note": slovenia_note,
        "days_baby": days_baby,
        "seed_rate_g_m2": seed_rate_g_m2,
        "seed_spacing_cm": seed_spacing_cm,
        "row_spacing_cm": row_spacing_cm,
    }
    calendar = default_calendar_for_crop(crop, category)
    for field in CALENDAR_FIELDS:
        item[field] = calendar.get(field)
    if item.get("calendar_source_url") is None:
        item["calendar_source_url"] = source_url
    return item


EU_SEED_CATALOG = [
    eu_variety(
        "Baby leaf hrastov list", "Asteraceae", "Oaking", 30,
        "Enza Zaden / Vitalis",
        "https://www.enzazaden.com/nordics/products-and-services/our-products/lettuce/Oaking",
        "Zelen hrastov list za baby leaf; temno zeleni, sijoči in debelejši listi, visok izplen in dobra obstojnost. HR Bl:29-41EU/Nr:0; IR LMV:1.",
        "Profesionalna evropska sorta. Primarni tip v GrowMasterju: Hrastov list zelen. Dobavljivost preveri pri Enza/Vitalis EU zastopniku.",
        category="Baby leaf", seed_forms="navadno, ekološko", days_baby=30,
        seed_rate_g_m2=1.2,
    ),
    eu_variety(
        "Baby leaf hrastov list", "Asteraceae", "Digitale", 30,
        "Enza Zaden / Vitalis",
        "https://www.enzazaden.com/nordics/products-and-services/our-products/lettuce/Digitale",
        "Rdeč hrastov list za baby leaf; temno sijoča rdeča barva, tanjše steblo in dober izplen. HR Bl:29-41EU/Nr:0/TBSV; IR LMV:1.",
        "Profesionalna evropska sorta. Primarni tip v GrowMasterju: Hrastov list rdeč. Dobavljivost preveri pri Enza/Vitalis EU zastopniku.",
        category="Baby leaf", seed_forms="navadno, ekološko", days_baby=30,
        seed_rate_g_m2=1.2,
    ),
    eu_variety(
        "Solata", "Asteraceae", "Piro", 50,
        "Amarant / EU",
        "https://www.amarant.si/eko-seme-solata-piro",
        "Zelen hrastov list, primeren predvsem za poletno pridelavo; lahko se obira po listih ali kot cela rozeta.",
        "Neposredno dobavljivo v Sloveniji pri Amarantu; poreklo EU. Agronomski tip: Hrastov list zelen.",
        seed_forms="ekološko", seed_spacing_cm=20.0, row_spacing_cm=20.0,
    ),
    eu_variety(
        "Redkvica", "Brassicaceae", "Saxa", 30,
        "Amarant / EU",
        "https://www.amarant.si/eko-seme-redkvica-saxa",
        "Klasična rdeča okrogla redkvica za spomladanske in jesenske setve.",
        "Neposredno dobavljivo v Sloveniji; Amarant navaja poreklo EU in profesionalna pakiranja do 100 g.",
        seed_forms="ekološko", seed_spacing_cm=2.0, row_spacing_cm=20.0,
    ),
    eu_variety(
        "Rdeča pesa", "Amaranthaceae", "Detroit 2", 60,
        "Amarant / Slovenija-EU",
        "https://www.amarant.si/eko-seme-rdeca-pesa-detroit",
        "Okrogla rdeča pesa za glavno sezono; primerna tudi za večja pakiranja semena.",
        "Neposredno dobavljivo v Sloveniji; navedeno poreklo Slovenija/EU, pakiranja do 1 kg.",
        seed_forms="ekološko", seed_spacing_cm=7.5, row_spacing_cm=20.0,
    ),
    eu_variety(
        "Rdeča pesa", "Amaranthaceae", "Forono", 65,
        "Amarant / EU",
        "https://www.amarant.si/eko-seme-rdeca-pesa-forono",
        "Podolgovata pesa z enakomerno temno rdečo obarvanostjo in izenačenimi rezinami.",
        "Neposredno dobavljivo v Sloveniji; poreklo EU, pakiranja do 1 kg.",
        seed_forms="ekološko", seed_spacing_cm=7.5, row_spacing_cm=20.0,
    ),
    eu_variety(
        "Radič", "Asteraceae", "Tržaški solatnik", 55,
        "Amarant",
        "https://www.amarant.si/eko-seme-radic-trzaski-solatnik",
        "Zuccherina di Trieste; listni radič primeren za gosto direktno setev in večkratno rezanje.",
        "Neposredno dobavljivo v Sloveniji; primeren tudi za baby-leaf način pridelave.",
        seed_forms="ekološko", seed_spacing_cm=1.0, row_spacing_cm=10.0,
    ),
    eu_variety(
        "Pak Choi", "Brassicaceae", "Green Revolution F1", 45,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product/pak-choi-green-revolution-f1/",
        "Zelenostebelni pak choi s počasnejšim uhajanjem v cvet, kompaktno pokončno rastjo in dobro maso glav.",
        "Evropski profesionalni katalog. Primeren predvsem za pomlad in jesen; v Sloveniji smiseln za polje in zaščiten prostor.",
        category="Azijska", seed_forms="profesionalno seme", seed_spacing_cm=20.0, row_spacing_cm=25.0,
    ),
    eu_variety(
        "Pak Choi", "Brassicaceae", "Summer Breeze F1", 45,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product/pak-choi-summer-breeze-f1",
        "Toplotno tolerantnejši pak choi za poletne in jesenske termine; visok delež listov, odpornost proti bakterijski mehki gnilobi in beli rji.",
        "Evropski profesionalni katalog; zanimiv za toplejše termine v Sloveniji.",
        category="Azijska", seed_forms="profesionalno seme", seed_spacing_cm=20.0, row_spacing_cm=25.0,
    ),
    eu_variety(
        "Mizuna", "Brassicaceae", "Mizuna F1", 30,
        "Takii Europe",
        "https://takii.eu/products/orgr-mizuna-f1/",
        "Hibridna mizuna s kratkim ciklom, visoko izenačenostjo, kompaktno rastjo, zelenimi listi in belimi stebli; za celoletno pridelavo.",
        "Evropski profesionalni Takii katalog. Primerna za azijski baby leaf in polno velikost.",
        category="Azijska", seed_forms="profesionalno seme", days_baby=24, seed_rate_g_m2=2.5,
    ),
    eu_variety(
        "Baby leaf gorčica", "Brassicaceae", "Golden Streaks", 25,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product-category/leaf/?country=EU",
        "Zelo produktivna cut-and-come-again baby-leaf gorčica z nežno razrezanim zelenim listom in blago pikantnim okusom.",
        "Evropski profesionalni katalog; primerna za pikantne baby-leaf mešanice.",
        category="Baby leaf", seed_forms="profesionalno seme", days_baby=25, seed_rate_g_m2=2.5,
    ),
    eu_variety(
        "Baby leaf gorčica", "Brassicaceae", "Ruby Streaks", 25,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product-category/leaf/?country=EU",
        "Rdeča fino narezana gorčica z zelenimi žilami, blagega sladkastega gorčičnega okusa.",
        "Evropski profesionalni katalog; primerna za barvne baby-leaf mešanice.",
        category="Baby leaf", seed_forms="profesionalno seme", days_baby=25, seed_rate_g_m2=2.5,
    ),
    eu_variety(
        "Tatsoi", "Brassicaceae", "Tah Tsai", 40,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product-category/leaf/?country=EU",
        "Hladno toleranten tatsoi; v evropskem katalogu naveden tudi za baby leaf.",
        "Evropsko dobavljiva azijska kultura. Za celo glavo lahko hitreje uide v cvet; za baby leaf je primernejša gosta setev.",
        category="Azijska", seed_forms="profesionalno seme", days_baby=25, seed_rate_g_m2=2.5,
    ),
    eu_variety(
        "Koriander", "Apiaceae", "Rumba", 40,
        "Tozer Seeds Europe",
        "https://www.tozerseeds.com/product-category/leaf/?country=EU",
        "Temni listi, visok pridelek in pokončna rast za lažje spravilo; primeren za poletno pridelavo v hladnejšem podnebju.",
        "Evropski profesionalni vir za dhania/koriander; prednost pred uvozom semena izven Evrope.",
        category="Indijska", seed_forms="profesionalno seme", seed_rate_g_m2=6.0,
    ),
]
