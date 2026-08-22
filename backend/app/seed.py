from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.johnnys_catalog import JOHNNYS_SLOVENIA_VARIETIES
from app.maturity import estimated_seasonal_days
from app.models import Bed, Crop, Farm, Task, Variety


CROP_DATA = [
    {
        "name": "Rukola",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Astro", 35), ("Coltivata", 30), ("Sylvetta", 40)],
    },
    {
        "name": "Solata",
        "family": "Asteraceae",
        "category": "Domača",
        "varieties": [
            ("Ljubljanska ledenka", 65),
            ("Posavka", 60),
            ("Leda", 60),
            ("Majska kraljica", 55),
            ("Lollo Rosso", 45),
            ("Batavia", 50),
        ],
    },
    {
        "name": "Paradižnik",
        "family": "Solanaceae",
        "category": "Domača",
        "varieties": [
            ("Val", 125),
            ("Begunec", 120),
            ("Volovsko srce", 135),
            ("San Marzano", 130),
        ],
    },
    {
        "name": "Paprika",
        "family": "Solanaceae",
        "category": "Domača",
        "varieties": [
            ("Alpina", 135),
            ("Jerneja", 140),
            ("Sivrija", 135),
            ("Magdalena", 140),
            ("Kurtovska kapija", 145),
        ],
    },
    {
        "name": "Feferon",
        "family": "Solanaceae",
        "category": "Domača",
        "varieties": [("Eta", 135), ("Cayenne", 125)],
    },
    {
        "name": "Jajčevec",
        "family": "Solanaceae",
        "category": "Domača",
        "varieties": [("Black Beauty", 130), ("Listada de Gandia", 125)],
    },
    {
        "name": "Kumara",
        "family": "Cucurbitaceae",
        "category": "Domača",
        "varieties": [
            ("Dolga zelena", 65),
            ("Marketmore", 70),
            ("Pariški kornišon", 60),
        ],
    },
    {
        "name": "Bučka",
        "family": "Cucurbitaceae",
        "category": "Domača",
        "varieties": [("Black Beauty", 55), ("Genovese", 55), ("Gold Rush", 55)],
    },
    {
        "name": "Buča",
        "family": "Cucurbitaceae",
        "category": "Domača",
        "varieties": [
            ("Slovenska golica", 110),
            ("Hokkaido", 95),
            ("Butternut", 110),
        ],
    },
    {
        "name": "Fižol",
        "family": "Fabaceae",
        "category": "Domača",
        "varieties": [
            ("KIS Amand", 60),
            ("KIS Marcelijan", 60),
            ("Češnjevec", 75),
            ("Jabelski pisanec", 85),
            ("Ptujski maslenec", 80),
        ],
    },
    {
        "name": "Grah",
        "family": "Fabaceae",
        "category": "Domača",
        "varieties": [("Vitičar", 70), ("Kelvedon Wonder", 65), ("Telefon", 80)],
    },
    {
        "name": "Bob",
        "family": "Fabaceae",
        "category": "Domača",
        "varieties": [("Matko", 90), ("Videk", 90)],
    },
    {
        "name": "Korenje",
        "family": "Apiaceae",
        "category": "Domača",
        "varieties": [("Nantes", 95), ("Flaker", 110), ("Chantenay", 90)],
    },
    {
        "name": "Rdeča pesa",
        "family": "Amaranthaceae",
        "category": "Domača",
        "varieties": [("Detroit", 60), ("Cylindra", 65), ("Chioggia", 60)],
    },
    {
        "name": "Redkvica",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Saxa", 30), ("Cherry Belle", 28), ("French Breakfast", 30)],
    },
    {
        "name": "Čebula",
        "family": "Amaryllidaceae",
        "category": "Domača",
        "varieties": [("Ptujska rdeča", 125), ("Tera", 120), ("Belokranjka", 120)],
    },
    {
        "name": "Por",
        "family": "Amaryllidaceae",
        "category": "Domača",
        "varieties": [("Dolgi domači", 130), ("Carentan", 130)],
    },
    {
        "name": "Česen",
        "family": "Amaryllidaceae",
        "category": "Domača",
        "varieties": [
            ("Ptujski jesenski", 240),
            ("Ptujski spomladanski", 150),
            ("Haloški", 240),
            ("Primorski", 220),
        ],
    },
    {
        "name": "Zelje",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [
            ("Ljubljansko", 105),
            ("Nanoško", 120),
            ("Varaždinsko 2", 110),
            ("Futoško", 110),
        ],
    },
    {
        "name": "Cvetača",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Snowball", 90), ("Romanesco", 100)],
    },
    {
        "name": "Brokoli",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Calabrese", 85), ("Belstar", 85)],
    },
    {
        "name": "Koleraba",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Dunajska bela", 60), ("Superschmelz", 80)],
    },
    {
        "name": "Repa",
        "family": "Brassicaceae",
        "category": "Domača",
        "varieties": [("Kranjska podolgovata", 65), ("Kranjska okrogla", 60)],
    },
    {
        "name": "Špinača",
        "family": "Amaranthaceae",
        "category": "Domača",
        "varieties": [("Matador", 45), ("Winter Giant", 50)],
    },
    {
        "name": "Blitva",
        "family": "Amaranthaceae",
        "category": "Domača",
        "varieties": [("Lukullus", 55), ("Bright Lights", 55)],
    },
    {
        "name": "Endivija",
        "family": "Asteraceae",
        "category": "Domača",
        "varieties": [("Dečja glava", 85), ("Eskariol zelena", 80)],
    },
    {
        "name": "Motovilec",
        "family": "Caprifoliaceae",
        "category": "Domača",
        "varieties": [("Holandski", 55), ("Verte de Cambrai", 60)],
    },
    {
        "name": "Radič",
        "family": "Asteraceae",
        "category": "Domača",
        "varieties": [("Tržaški solatnik", 55), ("Palla Rossa", 90), ("Castelfranco", 90)],
    },
    {
        "name": "Krompir",
        "family": "Solanaceae",
        "category": "Domača",
        "varieties": [("KIS Sora", 110), ("Kresnik", 85), ("Desiree", 110)],
    },
    {
        "name": "Peteršilj",
        "family": "Apiaceae",
        "category": "Domača",
        "varieties": [("Domači listnik", 75), ("Berlinski", 150)],
    },
    {
        "name": "Zelena",
        "family": "Apiaceae",
        "category": "Domača",
        "varieties": [("Praška", 150), ("Tango", 120)],
    },
    {
        "name": "Koromač",
        "family": "Apiaceae",
        "category": "Domača",
        "varieties": [("Romanesco", 90), ("Finale", 85)],
    },
    {
        "name": "Mizuna",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Green", 30), ("Red", 35), ("Kyona", 30)],
    },
    {
        "name": "Pak Choi",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Joi Choi", 45), ("Mei Qing Choi", 45), ("Shanghai Green", 40)],
    },
    {
        "name": "Tatsoi",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Rosette", 45), ("Koji", 45)],
    },
    {
        "name": "Komatsuna",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Green River", 35), ("Carlton", 40)],
    },
    {
        "name": "Choi Sum",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Green 70 D Improved", 42), ("Hon Tsai Tai", 45)],
    },
    {
        "name": "Kailan",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Suiho", 60), ("Green Lance", 55)],
    },
    {
        "name": "Daikon",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Minowase", 60), ("Miyashige", 65)],
    },
    {
        "name": "Pekinško zelje",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Michihili", 75), ("Tokyo Bekana", 45)],
    },
    {
        "name": "Mibuna",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Early", 35), ("Green Spray", 40)],
    },
    {
        "name": "Japonska repa",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Hakurei", 38), ("Tokyo Cross", 35)],
    },
    {
        "name": "Azijska gorčica",
        "family": "Brassicaceae",
        "category": "Azijska",
        "varieties": [("Green Wave", 45), ("Red Giant", 40)],
    },
    {
        "name": "Shiso",
        "family": "Lamiaceae",
        "category": "Azijska",
        "varieties": [("Green Shiso", 60), ("Red Shiso", 60)],
    },
    {
        "name": "Shungiku",
        "family": "Asteraceae",
        "category": "Azijska",
        "varieties": [("Serrated", 45), ("Oasis", 45)],
    },
    {
        "name": "Edamame",
        "family": "Fabaceae",
        "category": "Azijska",
        "varieties": [("Midori Giant", 85), ("Envy", 75)],
    },
    {
        "name": "Methi",
        "family": "Fabaceae",
        "category": "Indijska",
        "varieties": [("Indian Fenugreek", 30), ("Kasuri", 35)],
    },
    {
        "name": "Bamija",
        "family": "Malvaceae",
        "category": "Indijska",
        "varieties": [("Arka Anamika", 55), ("Pusa Bhindi-5", 55), ("Clemson Spineless", 55)],
    },
    {
        "name": "Karela",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Pusa Aushadhi", 50), ("Pusa Rasdar", 43), ("Kashi Pratishtha", 55)],
    },
    {
        "name": "Lauki",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Pusa Naveen", 65), ("Arka Bahar", 70), ("Kashi Ganga", 65)],
    },
    {
        "name": "Rebrasta bučka",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Arka Prasan", 45), ("Pusa Nasdar", 55)],
    },
    {
        "name": "Gobasta bučka",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Pusa Chikni", 55), ("Kashi Divya", 55)],
    },
    {
        "name": "Tinda",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Pusa Tinda", 60), ("Tinda Ludhiana", 60)],
    },
    {
        "name": "Voščena buča",
        "family": "Cucurbitaceae",
        "category": "Indijska",
        "varieties": [("Kashi Ujwal", 90), ("Indu", 100)],
    },
    {
        "name": "Indijski jajčevec",
        "family": "Solanaceae",
        "category": "Indijska",
        "varieties": [("Pusa Purple Long", 120), ("Pusa Shyamla", 125), ("Kashi Uttam", 120)],
    },
    {
        "name": "Indijski čili",
        "family": "Solanaceae",
        "category": "Indijska",
        "varieties": [("Pusa Jwala", 130), ("Pusa Sadabahar", 140), ("Byadgi", 150)],
    },
    {
        "name": "Malabarska špinača",
        "family": "Basellaceae",
        "category": "Indijska",
        "varieties": [("Green Stem", 55), ("Red Stem", 55)],
    },
    {
        "name": "Listni amarant",
        "family": "Amaranthaceae",
        "category": "Indijska",
        "varieties": [("Chaulai Green", 30), ("Chaulai Red", 35)],
    },
    {
        "name": "Palak",
        "family": "Amaranthaceae",
        "category": "Indijska",
        "varieties": [("Pusa All Green", 40), ("Jobner Green", 45)],
    },
    {
        "name": "Guar",
        "family": "Fabaceae",
        "category": "Indijska",
        "varieties": [("Pusa Navbahar", 60), ("HG 365", 65)],
    },
    {
        "name": "Koriander",
        "family": "Apiaceae",
        "category": "Indijska",
        "varieties": [("CO-4", 40), ("Sadhana", 45)],
    },
    {
        "name": "Baby leaf mešanica",
        "family": "Mešanica",
        "category": "Baby leaf",
        "varieties": [
            (
                "Klasična solatna mešanica",
                28,
                24,
                35,
                50,
                "Zelena in rdeča listna solata, baby špinača, mladi listi "
                "rdeče pese, blitva in rukola.",
            ),
            (
                "Azijska mešanica",
                25,
                22,
                32,
                45,
                "Mizuna, mibuna, tatsoi, mladi pak choi in komatsuna.",
            ),
            (
                "Pikantna mešanica",
                25,
                22,
                32,
                45,
                "Divja rukola, azijska gorčica, rdeča mizuna, listna "
                "redkvica in baby ohrovt.",
            ),
        ],
    },
    {
        "name": "Divja rukola",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Sylvetta", 35, 30, 42, 60),
            ("Selvatica", 38, 32, 45, 65),
        ],
    },
    {
        "name": "Salatni trpotec",
        "family": "Plantaginaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Erba Stella", 45, 38, 55, 75),
            ("Minutina", 45, 38, 55, 75),
        ],
    },
    {
        "name": "Cikorija",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Catalogna", 55, 48, 65, 90),
            ("Puntarelle", 65, 55, 75, 100),
            ("Grumolo Verde", 70, 60, 85, 115),
        ],
    },
    {
        "name": "Mladi listi rdeče pese",
        "family": "Amaranthaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Bull's Blood", 25, 22, 32, 45),
            ("Detroit Baby Leaf", 28, 24, 35, 50),
            ("Rainbow Mix", 28, 24, 35, 50),
        ],
    },
    {
        "name": "Baby leaf špinača",
        "family": "Amaranthaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Matador", 30, 25, 38, 55),
            ("Palco", 28, 24, 35, 50),
            ("Space", 28, 24, 35, 50),
        ],
    },
    {
        "name": "Baby leaf ohrovt",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Nero di Toscana", 30, 26, 38, 55),
            ("Red Russian", 28, 24, 35, 50),
            ("Dwarf Green Curled", 30, 26, 38, 55),
        ],
    },
    {
        "name": "Baby leaf listna solata",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Green Saladbowl", 28, 24, 34, 48),
            ("Red Saladbowl", 30, 26, 36, 50),
            ("Tango", 28, 24, 34, 48),
            ("Red Sails", 30, 26, 36, 50),
            ("Black Seeded Simpson", 28, 24, 34, 48),
            ("Marilisa", 30, 26, 36, 50),
        ],
    },
    {
        "name": "Baby leaf hrastov list",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Garrison", 28, 24, 34, 48),
            ("Green Oakleaf", 28, 24, 34, 48),
            ("Red Oakleaf", 30, 26, 36, 50),
        ],
    },
    {
        "name": "Baby leaf rimska solata",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Parris Island", 30, 26, 36, 50),
            ("Jericho", 28, 24, 34, 48),
            ("Outredgeous", 32, 27, 38, 52),
        ],
    },
    {
        "name": "Baby leaf batavia",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Nevada", 32, 28, 40, 55),
            ("Maravilla de Verano", 32, 28, 40, 55),
            ("Leda", 32, 28, 40, 55),
        ],
    },
    {
        "name": "Baby leaf endivija",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Frisée", 32, 28, 40, 55),
            ("Dečja glava", 35, 30, 43, 60),
            ("Wallonne", 38, 32, 46, 65),
        ],
    },
    {
        "name": "Baby leaf radič",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [
            ("Tržaški solatnik", 30, 26, 38, 52),
            ("Palla Rossa", 35, 30, 44, 60),
            ("Castelfranco", 35, 30, 44, 60),
        ],
    },
    {
        "name": "Baby leaf blitva",
        "family": "Amaranthaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Bright Lights", 28, 24, 35, 48),
            ("Charbell", 25, 22, 32, 45),
            ("Bright Yellow", 25, 22, 32, 45),
        ],
    },
    {
        "name": "Baby leaf gorčica",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Red Giant", 25, 21, 31, 43),
            ("Green Wave", 25, 21, 31, 43),
            ("Ruby Streaks", 25, 21, 31, 43),
            ("Wasabina", 25, 21, 31, 43),
            ("Scarlet Frills", 25, 21, 31, 43),
        ],
    },
    {
        "name": "Baby leaf mizuna",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Green River", 24, 20, 30, 42),
            ("Red Kingdom", 25, 21, 31, 43),
            ("Ember", 25, 21, 31, 43),
        ],
    },
    {
        "name": "Baby leaf tatsoi",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Koji", 28, 23, 34, 46),
            ("Red Cloud", 28, 23, 34, 46),
            ("Tatsoi", 28, 23, 34, 46),
        ],
    },
    {
        "name": "Baby leaf pak choi",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Rosie", 28, 23, 34, 46),
            ("Joi Choi", 28, 23, 34, 46),
            ("Mei Qing Choi", 28, 23, 34, 46),
        ],
    },
    {
        "name": "Baby leaf komatsuna",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Green River", 25, 21, 31, 43),
            ("Green Giant", 25, 21, 31, 43),
            ("Carlton", 27, 23, 33, 45),
        ],
    },
    {
        "name": "Baby leaf kitajsko zelje",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [
            ("Tokyo Bekana", 25, 21, 32, 45),
            ("Michihili", 28, 23, 34, 48),
            ("Kyoto No. 3", 28, 23, 34, 48),
        ],
    },
]
DEMO_FARM_NAME = "GrowMaster Demo Farm"


def seed_database(db: Session) -> None:
    farm = db.scalar(select(Farm).limit(1))
    if farm is None:
        farm = Farm(name=DEMO_FARM_NAME)
        db.add(farm)
        db.flush()

        previous_families = {
            "A1": "Brassicaceae",
            "A2": "Asteraceae",
        }
        for index in range(1, 7):
            name = f"A{index}"
            db.add(
                Bed(
                    farm_id=farm.id,
                    name=name,
                    width_m=0.8,
                    length_m=15.0,
                    status="empty",
                    last_crop_family=previous_families.get(name),
                )
            )
        db.flush()

    existing_crops = {
        crop.name.casefold(): crop
        for crop in db.scalars(
            select(Crop).options(selectinload(Crop.varieties))
        ).all()
    }
    legacy_categories = {
        "Asian": "Azijska",
        "Indian": "Indijska",
    }
    for item in CROP_DATA:
        crop = existing_crops.get(item["name"].casefold())
        if crop is None:
            crop = Crop(
                name=item["name"],
                family=item["family"],
                category=item["category"],
            )
            db.add(crop)
            db.flush()
            existing_crops[crop.name.casefold()] = crop
        elif crop.category == "Baby leaf" and item["category"] != "Baby leaf":
            crop.category = item["category"]
        elif crop.category in legacy_categories:
            crop.category = legacy_categories[crop.category]

        existing_varieties = {
            variety.name.casefold(): variety for variety in crop.varieties
        }
        for variety_values in item["varieties"]:
            name = variety_values[0]
            composition = variety_values[5] if len(variety_values) == 6 else None
            existing_variety = existing_varieties.get(name.casefold())
            if existing_variety is not None:
                if composition and not existing_variety.composition:
                    existing_variety.composition = composition
                continue
            if len(variety_values) == 2:
                days_to_harvest = variety_values[1]
                estimates = estimated_seasonal_days(days_to_harvest)
            else:
                _, spring, summer, autumn, winter = variety_values[:5]
                days_to_harvest = spring
                estimates = {
                    "spring": spring,
                    "summer": summer,
                    "autumn": autumn,
                    "winter": winter,
                }
            crop.varieties.append(
                Variety(
                    name=name,
                    days_to_harvest=days_to_harvest,
                    days_spring=estimates["spring"],
                    days_summer=estimates["summer"],
                    days_autumn=estimates["autumn"],
                    days_winter=estimates["winter"],
                    composition=composition,
                )
            )
            existing_varieties[name.casefold()] = crop.varieties[-1]

    # Supplier catalog enrichment is additive: an existing crop or variety is
    # never removed and its maturity values are never overwritten.  Missing
    # metadata is filled, while user-entered metadata remains authoritative.
    metadata_fields = (
        "source_name",
        "source_url",
        "seed_forms",
        "traits",
        "slovenia_note",
        "days_baby",
        "seed_rate_g_m2",
        "seed_spacing_cm",
        "row_spacing_cm",
    )
    for item in JOHNNYS_SLOVENIA_VARIETIES:
        crop = existing_crops.get(item["crop"].casefold())
        if crop is None:
            crop = Crop(
                name=item["crop"],
                family=item["family"],
                category=item["category"],
            )
            db.add(crop)
            db.flush()
            existing_crops[crop.name.casefold()] = crop
        existing_varieties = {
            variety.name.casefold(): variety for variety in crop.varieties
        }
        existing_variety = existing_varieties.get(item["name"].casefold())
        if existing_variety is not None:
            for field in metadata_fields:
                if getattr(existing_variety, field) is None and item[field] is not None:
                    setattr(existing_variety, field, item[field])
            continue
        estimates = estimated_seasonal_days(item["days"])
        crop.varieties.append(
            Variety(
                name=item["name"],
                days_to_harvest=item["days"],
                days_spring=estimates["spring"],
                days_summer=estimates["summer"],
                days_autumn=estimates["autumn"],
                days_winter=estimates["winter"],
                composition=None,
                **{field: item[field] for field in metadata_fields},
            )
        )
    db.flush()

    if db.scalar(select(Task).limit(1)) is None and farm.name == DEMO_FARM_NAME:
        beds = {bed.name: bed for bed in db.scalars(select(Bed)).all()}
        today = date.today()
        db.add_all(
            [
                Task(
                    farm_id=farm.id,
                    title="Jutranji pregled vseh gredic",
                    task_type="inspection",
                    due_date=today,
                    priority="normal",
                ),
                Task(
                    farm_id=farm.id,
                    title="Preveri namakalni sistem",
                    task_type="irrigation",
                    due_date=today,
                    priority="high",
                ),
                Task(
                    farm_id=farm.id,
                    bed_id=beds.get("A3").id if beds.get("A3") else None,
                    title="Pripravi gredico A3 za setev",
                    task_type="bed_preparation",
                    due_date=today,
                    priority="normal",
                ),
            ]
        )

    db.commit()
