import base64
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile

from sqlalchemy import Integer, func, select, text
from sqlalchemy.orm import Session

from app.database import Base
from app.maturity import estimated_seasonal_days
from app.migrations import latest_revision
import app.models  # noqa: F401  Ensures every mapped table is registered.


BACKUP_FORMAT = "growmaster-portable-backup"
BACKUP_FORMAT_VERSION = 1
BACKUP_SCHEMA_REVISION = "0001_current_schema"
SECURITY_TABLES = {"admin_credentials", "auth_sessions"}
MAX_BACKUP_BYTES = 25 * 1024 * 1024
AUTOMATIC_BACKUP_RETENTION = 10
AUTOMATIC_BACKUP_PATTERN = re.compile(
    r"^growmaster-auto-\d{8}T\d{6}Z-[0-9a-f]{8}\.json$"
)
DAILY_BACKUP_RETENTION = 14
DAILY_BACKUP_PATTERN = re.compile(
    r"^growmaster-daily-(\d{8})-[0-9a-f]{8}\.json$"
)


class BackupValidationError(ValueError):
    pass


class BackupRestoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedBackup:
    rows_by_table: dict[str, list[dict]]
    record_count: int
    created_at: str


def backup_directory() -> Path:
    return Path(os.getenv("BACKUP_DIR", "backups"))


def backup_storage_status() -> dict:
    """Verify that the configured backup directory accepts an atomic local write."""
    directory = backup_directory()
    probe_path: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix=".growmaster-storage-check-",
            delete=False,
        ) as probe:
            probe.write(b"growmaster")
            probe.flush()
            os.fsync(probe.fileno())
            probe_path = Path(probe.name)
        probe_path.unlink()
        return {
            "ok": True,
            "detail": "Mapa za varnostne kopije je zapisljiva.",
        }
    except OSError:
        return {
            "ok": False,
            "detail": "Mapa za varnostne kopije ni zapisljiva.",
        }
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except OSError:
                pass


def backup_tables() -> list:
    """Return portable business-data tables, never credentials or live sessions."""
    return [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in SECURITY_TABLES
    ]


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encode_value(value: object) -> object:
    if isinstance(value, bytes):
        return {
            "$growmaster_type": "bytes",
            "value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, datetime):
        return {"$growmaster_type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$growmaster_type": "date", "value": value.isoformat()}
    return value


def decode_value(value: object) -> object:
    if not isinstance(value, dict):
        if isinstance(value, list):
            raise BackupValidationError("Varnostna kopija vsebuje neveljavno vrednost.")
        return value
    if set(value) != {"$growmaster_type", "value"}:
        raise BackupValidationError("Varnostna kopija vsebuje neznano vrsto vrednosti.")
    value_type = value["$growmaster_type"]
    encoded = value["value"]
    if not isinstance(encoded, str):
        raise BackupValidationError("Kodirana vrednost varnostne kopije ni veljavna.")
    try:
        if value_type == "bytes":
            return base64.b64decode(encoded, validate=True)
        if value_type == "datetime":
            return datetime.fromisoformat(encoded)
        if value_type == "date":
            return date.fromisoformat(encoded)
    except (ValueError, TypeError) as error:
        raise BackupValidationError(
            "Varnostna kopija vsebuje poškodovano kodirano vrednost."
        ) from error
    raise BackupValidationError("Varnostna kopija vsebuje neznano vrsto vrednosti.")


def database_summary(db: Session) -> dict:
    tables = backup_tables()
    counts = {
        table.name: db.scalar(select(func.count()).select_from(table)) or 0
        for table in tables
    }
    return {
        "schema_revision": latest_revision(),
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "table_count": len(tables),
        "record_count": sum(counts.values()),
        "records_by_table": counts,
        "maximum_restore_size_mb": MAX_BACKUP_BYTES // (1024 * 1024),
    }


def create_backup_bytes(db: Session) -> tuple[bytes, dict]:
    tables: dict[str, list[dict]] = {}
    record_count = 0
    for table in backup_tables():
        rows = db.execute(select(table)).mappings().all()
        tables[table.name] = [
            {key: encode_value(value) for key, value in dict(row).items()}
            for row in rows
        ]
        record_count += len(rows)

    payload = {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "schema_revision": BACKUP_SCHEMA_REVISION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table_count": len(tables),
        "record_count": record_count,
        "tables": tables,
    }
    checksum = hashlib.sha256(canonical_json(payload)).hexdigest()
    document = {"checksum_sha256": checksum, "payload": payload}
    content = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    return content, {
        "checksum_sha256": checksum,
        "created_at": payload["created_at"],
        "table_count": payload["table_count"],
        "record_count": record_count,
        "size_bytes": len(content),
    }


def parse_backup(content: bytes) -> ParsedBackup:
    if not content:
        raise BackupValidationError("Izbrana varnostna kopija je prazna.")
    if len(content) > MAX_BACKUP_BYTES:
        raise BackupValidationError(
            f"Varnostna kopija je večja od {MAX_BACKUP_BYTES // (1024 * 1024)} MB."
        )
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupValidationError(
            "Datoteka ni veljavna GrowMaster varnostna kopija."
        ) from error
    if not isinstance(document, dict) or set(document) != {
        "checksum_sha256",
        "payload",
    }:
        raise BackupValidationError("Zgradba varnostne kopije ni veljavna.")
    payload = document["payload"]
    checksum = document["checksum_sha256"]
    if not isinstance(payload, dict) or not isinstance(checksum, str):
        raise BackupValidationError("Zgradba varnostne kopije ni veljavna.")
    calculated = hashlib.sha256(canonical_json(payload)).hexdigest()
    if not hmac.compare_digest(checksum, calculated):
        raise BackupValidationError(
            "Nadzorna vsota se ne ujema; datoteka je poškodovana ali spremenjena."
        )
    if payload.get("format") != BACKUP_FORMAT:
        raise BackupValidationError("Datoteka ni GrowMaster varnostna kopija.")
    if payload.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupValidationError("Različica zapisa varnostne kopije ni podprta.")
    if payload.get("schema_revision") != BACKUP_SCHEMA_REVISION:
        raise BackupValidationError(
            "Varnostna kopija pripada drugi različici podatkovne baze."
        )
    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, dict):
        raise BackupValidationError("Seznam tabel v varnostni kopiji ni veljaven.")

    known_tables = {table.name: table for table in backup_tables()}
    if set(tables_payload) != set(known_tables):
        raise BackupValidationError(
            "Varnostna kopija nima vseh pričakovanih podatkovnih tabel."
        )

    rows_by_table: dict[str, list[dict]] = {}
    record_count = 0
    for table_name, table in known_tables.items():
        encoded_rows = tables_payload[table_name]
        if not isinstance(encoded_rows, list):
            raise BackupValidationError(
                f"Podatki tabele {table_name} niso v pričakovani obliki."
            )
        expected_columns = {column.name for column in table.columns}
        seasonal_columns = {
            "days_spring",
            "days_summer",
            "days_autumn",
            "days_winter",
        }
        allowed_columns = {frozenset(expected_columns)}
        if table_name == "varieties":
            allowed_columns.update(
                {
                    frozenset(expected_columns - {"composition"}),
                    frozenset(expected_columns - seasonal_columns),
                    frozenset(expected_columns - seasonal_columns - {"composition"}),
                }
            )
        decoded_rows: list[dict] = []
        for encoded_row in encoded_rows:
            row_columns = set(encoded_row) if isinstance(encoded_row, dict) else set()
            if frozenset(row_columns) not in allowed_columns:
                raise BackupValidationError(
                    f"Zapis v tabeli {table_name} nima pričakovanih polj."
                )
            decoded_row = {
                key: decode_value(value) for key, value in encoded_row.items()
            }
            if table_name == "varieties" and not seasonal_columns <= row_columns:
                estimates = estimated_seasonal_days(decoded_row["days_to_harvest"])
                decoded_row.update(
                    {
                        "days_spring": estimates["spring"],
                        "days_summer": estimates["summer"],
                        "days_autumn": estimates["autumn"],
                        "days_winter": estimates["winter"],
                    }
                )
            if table_name == "varieties" and "composition" not in row_columns:
                decoded_row["composition"] = None
            decoded_rows.append(decoded_row)
        rows_by_table[table_name] = decoded_rows
        record_count += len(decoded_rows)

    if payload.get("table_count") != len(known_tables):
        raise BackupValidationError("Število tabel v varnostni kopiji ni pravilno.")
    if payload.get("record_count") != record_count:
        raise BackupValidationError("Število zapisov v varnostni kopiji ni pravilno.")
    created_at = payload.get("created_at")
    if not isinstance(created_at, str):
        raise BackupValidationError("Datum varnostne kopije ni veljaven.")
    try:
        datetime.fromisoformat(created_at)
    except ValueError as error:
        raise BackupValidationError("Datum varnostne kopije ni veljaven.") from error
    return ParsedBackup(rows_by_table, record_count, created_at)


def write_automatic_backup(content: bytes, checksum: str) -> str:
    directory = backup_directory()
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"growmaster-auto-{timestamp}-{checksum[:8]}.json"
    target = directory / filename
    temporary = directory / f".{filename}.tmp"
    temporary.write_bytes(content)
    temporary.replace(target)
    automatic = sorted(
        (
            path
            for path in directory.glob("growmaster-auto-*.json")
            if AUTOMATIC_BACKUP_PATTERN.fullmatch(path.name)
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in automatic[AUTOMATIC_BACKUP_RETENTION:]:
        old_backup.unlink(missing_ok=True)
    return filename


def list_automatic_backups() -> list[dict]:
    directory = backup_directory()
    if not directory.exists():
        return []
    backups = []
    for path in directory.glob("growmaster-auto-*.json"):
        if not AUTOMATIC_BACKUP_PATTERN.fullmatch(path.name):
            continue
        stat = path.stat()
        backups.append(
            {
                "filename": path.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(),
            }
        )
    return sorted(backups, key=lambda item: item["created_at"], reverse=True)


def automatic_backup_path(filename: str) -> Path | None:
    if not AUTOMATIC_BACKUP_PATTERN.fullmatch(filename):
        return None
    path = backup_directory() / filename
    return path if path.is_file() else None


def _daily_backup_files() -> list[Path]:
    directory = backup_directory()
    if not directory.exists():
        return []
    return sorted(
        (
            path
            for path in directory.glob("growmaster-daily-*.json")
            if DAILY_BACKUP_PATTERN.fullmatch(path.name)
        ),
        key=lambda path: path.name,
        reverse=True,
    )


def _write_daily_backup(
    content: bytes,
    checksum: str,
    now: datetime | None = None,
) -> str:
    created_on = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    date_key = created_on.strftime("%Y%m%d")
    directory = backup_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"growmaster-daily-{date_key}-{checksum[:8]}.json"
    target = directory / filename
    temporary = directory / f".{filename}.tmp"
    temporary.write_bytes(content)
    temporary.replace(target)

    for path in _daily_backup_files():
        match = DAILY_BACKUP_PATTERN.fullmatch(path.name)
        if match and match.group(1) == date_key and path.name != filename:
            path.unlink(missing_ok=True)
    for old_backup in _daily_backup_files()[DAILY_BACKUP_RETENTION:]:
        old_backup.unlink(missing_ok=True)
    return filename


def refresh_daily_backup(db: Session, now: datetime | None = None) -> str:
    """Replace today's scheduled business-data snapshot with the current state."""
    content, summary = create_backup_bytes(db)
    return _write_daily_backup(
        content,
        summary["checksum_sha256"],
        now=now,
    )


def ensure_daily_backup(db: Session, now: datetime | None = None) -> str:
    """Create at most one scheduled snapshot for the given UTC calendar day."""
    created_on = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    date_key = created_on.strftime("%Y%m%d")
    for path in _daily_backup_files():
        match = DAILY_BACKUP_PATTERN.fullmatch(path.name)
        if match and match.group(1) == date_key:
            return path.name
    return refresh_daily_backup(db, now=created_on)


def list_daily_backups() -> list[dict]:
    backups = []
    for path in _daily_backup_files():
        stat = path.stat()
        match = DAILY_BACKUP_PATTERN.fullmatch(path.name)
        backups.append(
            {
                "filename": path.name,
                "backup_date": datetime.strptime(
                    match.group(1), "%Y%m%d"
                ).date().isoformat(),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(),
            }
        )
    return backups


def daily_backup_path(filename: str) -> Path | None:
    if not DAILY_BACKUP_PATTERN.fullmatch(filename):
        return None
    path = backup_directory() / filename
    return path if path.is_file() else None


def reset_postgres_sequences(db: Session) -> None:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    for table in backup_tables():
        for column in table.primary_key.columns:
            if not isinstance(column.type, Integer):
                continue
            sequence_name = db.scalar(
                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                {"table_name": table.name, "column_name": column.name},
            )
            if not sequence_name:
                continue
            maximum = db.scalar(select(func.max(column)))
            if maximum is None:
                db.execute(
                    text("SELECT setval(CAST(:sequence AS regclass), 1, false)"),
                    {"sequence": sequence_name},
                )
            else:
                db.execute(
                    text(
                        "SELECT setval(CAST(:sequence AS regclass), :maximum, true)"
                    ),
                    {"sequence": sequence_name, "maximum": maximum},
                )


def restore_parsed_backup(db: Session, backup: ParsedBackup) -> None:
    tables = backup_tables()
    try:
        for table in reversed(tables):
            db.execute(table.delete())
        for table in tables:
            rows = backup.rows_by_table[table.name]
            if rows:
                db.execute(table.insert(), rows)
        reset_postgres_sequences(db)
        db.commit()
    except Exception as error:
        db.rollback()
        raise BackupRestoreError(
            "Obnovitev ni uspela; prvotni podatki so ostali nespremenjeni."
        ) from error
