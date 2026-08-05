from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, select
from sqlalchemy.engine import Connection

from app.database import Base, engine
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


MIGRATIONS = (
    Migration("0001_current_schema", create_current_schema),
    Migration("0002_authentication", create_authentication_schema),
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
