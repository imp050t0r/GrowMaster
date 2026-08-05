from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bed, Crop, Farm, Variety


CROP_DATA = [
    {
        "name": "Rukola",
        "family": "Brassicaceae",
        "category": "Baby leaf",
        "varieties": [("Astro", 35), ("Coltivata", 30), ("Sylvetta", 40)],
    },
    {
        "name": "Mizuna",
        "family": "Brassicaceae",
        "category": "Asian",
        "varieties": [("Green", 30), ("Red", 35)],
    },
    {
        "name": "Solata",
        "family": "Asteraceae",
        "category": "Baby leaf",
        "varieties": [("Lollo Rosso", 45), ("Batavia", 50)],
    },
    {
        "name": "Methi",
        "family": "Fabaceae",
        "category": "Indian",
        "varieties": [("Indian Fenugreek", 30)],
    },
    {
        "name": "Pak Choi",
        "family": "Brassicaceae",
        "category": "Asian",
        "varieties": [("Joi Choi", 45)],
    },
    {
        "name": "Tatsoi",
        "family": "Brassicaceae",
        "category": "Asian",
        "varieties": [("Rosette", 45)],
    },
]


def seed_database(db: Session) -> None:
    farm = db.scalar(select(Farm).limit(1))
    if farm is None:
        farm = Farm(name="GrowMaster Demo Farm")
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

    if db.scalar(select(Crop).limit(1)) is None:
        for item in CROP_DATA:
            crop = Crop(
                name=item["name"],
                family=item["family"],
                category=item["category"],
            )
            crop.varieties = [
                Variety(name=name, days_to_harvest=days)
                for name, days in item["varieties"]
            ]
            db.add(crop)

    db.commit()
