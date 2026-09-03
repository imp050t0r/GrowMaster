from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect, select, text
from sqlalchemy.engine import Connection

from app.database import Base, engine
from app.maturity import estimated_seasonal_days
import app.models  # noqa: F401  Registers the complete schema before migrations run.


migration_metadata = MetaData()
schema_migrations = Table(
    "schema_migrations",
    migration_metadata,
    Column("revision", String(80), primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class Migration:
    revision: str
    upgrade: Callable[[Connection], None]


def create_current_schema(connection: Connection) -> None:
    """Create the current baseline without changing tables that already exist."""
    Base.metadata.create_all(bind=connection)


def create_authentication_schema(connection: Connection) -> None:
    """Add local credentials and sessions without changing business data."""
    app.models.AdminCredential.__table__.create(bind=connection, checkfirst=True)
    app.models.AuthSession.__table__.create(bind=connection, checkfirst=True)


def add_seasonal_maturity(connection: Connection) -> None:
    """Add four maturity estimates while retaining every existing variety."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    for column_name in ("days_spring", "days_summer", "days_autumn", "days_winter"):
        if column_name not in existing_columns:
            connection.execute(
                text(f"ALTER TABLE varieties ADD COLUMN {column_name} INTEGER")
            )
    rows = connection.execute(
        text(
            "SELECT id, days_to_harvest, days_spring, days_summer, "
            "days_autumn, days_winter FROM varieties"
        )
    ).mappings().all()
    for row in rows:
        estimates = estimated_seasonal_days(row["days_to_harvest"])
        connection.execute(
            text(
                "UPDATE varieties SET days_spring = :spring, days_summer = :summer, "
                "days_autumn = :autumn, days_winter = :winter WHERE id = :id"
            ),
            {
                "id": row["id"],
                "spring": row["days_spring"] or estimates["spring"],
                "summer": row["days_summer"] or estimates["summer"],
                "autumn": row["days_autumn"] or estimates["autumn"],
                "winter": row["days_winter"] or estimates["winter"],
            },
        )


def add_variety_composition(connection: Connection) -> None:
    """Add an optional human-readable recipe for seed and baby-leaf mixtures."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    if "composition" not in existing_columns:
        connection.execute(text("ALTER TABLE varieties ADD COLUMN composition TEXT"))


def add_variety_catalog_metadata(connection: Connection) -> None:
    """Add optional supplier facts without changing an existing catalog entry."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    columns = {
        "source_name": "VARCHAR(160)",
        "source_url": "TEXT",
        "seed_forms": "VARCHAR(240)",
        "traits": "TEXT",
        "slovenia_note": "TEXT",
        "days_baby": "INTEGER",
        "seed_rate_g_m2": "FLOAT",
        "seed_spacing_cm": "FLOAT",
        "row_spacing_cm": "FLOAT",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE varieties ADD COLUMN {column_name} "
                    f"{column_type}"
                )
            )


def add_variety_planting_calendar(connection: Connection) -> None:
    """Add optional timing guidance while retaining every catalog value."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    columns = {
        "planting_method": "VARCHAR(30)",
        "outdoor_months": "VARCHAR(40)",
        "protected_months": "VARCHAR(40)",
        "heat_tolerance": "VARCHAR(20)",
        "cold_tolerance": "VARCHAR(20)",
        "planting_calendar_note": "TEXT",
        "succession_interval_days": "INTEGER",
        "calendar_source_url": "TEXT",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE varieties ADD COLUMN {column_name} "
                    f"{column_type}"
                )
            )


def add_variety_harvest_profiles(connection: Connection) -> None:
    """Add optional propagation and harvest guidance without changing user data."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    columns = {
        "cultivation_methods": "VARCHAR(60)",
        "harvest_methods": "VARCHAR(160)",
        "nursery_days": "INTEGER",
        "direct_sow_extra_days": "INTEGER",
        "days_outer_leaf": "INTEGER",
        "regrowth_interval_min_days": "INTEGER",
        "regrowth_interval_max_days": "INTEGER",
        "max_regrowth_cuts": "INTEGER",
        "days_green_harvest": "INTEGER",
        "harvest_interval_days": "INTEGER",
        "harvest_duration_days": "INTEGER",
        "harvest_profile_note": "TEXT",
        "harvest_source_url": "TEXT",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE varieties ADD COLUMN {column_name} "
                    f"{column_type}"
                )
            )


def add_green_chilli_harvest(connection: Connection) -> None:
    """Complete harvest profiles for repeated green-fruit picking."""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("varieties")
    }
    columns = {
        "days_green_harvest": "INTEGER",
        "harvest_interval_days": "INTEGER",
        "harvest_duration_days": "INTEGER",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE varieties ADD COLUMN {column_name} "
                    f"{column_type}"
                )
            )


def create_inventory_write_offs(connection: Connection) -> None:
    """Add traceable inventory write-offs without rewriting harvest history."""
    app.models.InventoryWriteOff.__table__.create(bind=connection, checkfirst=True)


MIGRATIONS = (
    Migration("0001_current_schema", create_current_schema),
    Migration("0002_authentication", create_authentication_schema),
    Migration("0003_seasonal_maturity", add_seasonal_maturity),
    Migration("0004_variety_composition", add_variety_composition),
    Migration("0005_variety_catalog_metadata", add_variety_catalog_metadata),
    Migration("0006_variety_planting_calendar", add_variety_planting_calendar),
    Migration("0007_variety_harvest_profiles", add_variety_harvest_profiles),
    Migration("0008_green_chilli_harvest", add_green_chilli_harvest),
    Migration("0009_inventory_write_offs", create_inventory_write_offs),
)


def latest_revision() -> str:
    return MIGRATIONS[-1].revision


def run_migrations() -> str:
    """Apply each pending schema revision once and refuse unknown newer schemas."""
    with engine.begin() as connection:
        migration_metadata.create_all(bind=connection)
        applied = set(connection.execute(select(schema_migrations.c.revision)).scalars())
        known = {migration.revision for migration in MIGRATIONS}
        unknown = applied - known
        if unknown:
            revisions = ", ".join(sorted(unknown))
            raise RuntimeError(
                "Podatkovna baza uporablja novejšo ali neznano različico: "
                f"{revisions}. Zaženite ustrezno različico GrowMasterja."
            )
        seen_pending = False
        for migration in MIGRATIONS:
            if migration.revision not in applied:
                seen_pending = True
            elif seen_pending:
                raise RuntimeError(
                    "Zgodovina različic podatkovne baze ni zaporedna. "
                    "Pred zagonom obnovite preverjeno varnostno kopijo."
                )

        for migration in MIGRATIONS:
            if migration.revision in applied:
                continue
            migration.upgrade(connection)
            connection.execute(
                schema_migrations.insert().values(
                    revision=migration.revision,
                    applied_at=datetime.now(timezone.utc),
                )
            )
            applied.add(migration.revision)

    return latest_revision()
