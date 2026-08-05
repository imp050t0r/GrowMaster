# Data safety

GrowMaster keeps its PostgreSQL data and automatic recovery copies in separate Docker volumes. The **Podatki** screen provides a portable full backup and controlled restore workflow.

## Schema upgrades

The backend applies pending schema revisions before it seeds data or accepts requests. Applied revisions are recorded in the `schema_migrations` table and are never repeated. The first revision is an idempotent baseline: it creates missing tables on a fresh installation and safely adopts an existing GrowMaster database without deleting or replacing data.

Startup stops if the database contains an unknown newer revision. This prevents an older application image from silently opening a database it cannot understand.

## Portable backup

`GET /api/system/backups/export` downloads one JSON file containing every business-data table, including archived invoice PDFs. Authentication credentials and active sessions are deliberately excluded, so restoring a backup never replaces the current administrator password. Dates and binary values use explicit portable encodings. The document contains:

- backup-format and database-schema versions,
- creation time and record counts,
- every row from every GrowMaster data table,
- a SHA-256 checksum over the canonical payload.

The restore validator rejects an incomplete file, a changed checksum, an unsupported format, a different schema revision, unexpected tables or columns, malformed values and files larger than 25 MB.

## Controlled restore

The UI requires the exact confirmation `OBNOVI`. Before changing the database, GrowMaster writes a full automatic recovery copy of the current state. It then replaces application data in one database transaction. A failed insert rolls the whole transaction back, leaving the original data unchanged.

The ten newest automatic recovery copies are retained in the `growmaster_backups` Docker volume and can be downloaded from the **Podatki** screen. PostgreSQL identity sequences are moved to the restored maximum identifiers so new records continue safely.

## Operator recommendations

- Download a portable backup regularly and keep at least one copy outside the computer running GrowMaster.
- Keep backup files private: they can contain customer, invoice and financial data and are not encrypted.
- Download the newest automatic recovery copy after any restore until the restored data has been checked.
- Back up the Docker volumes before changing the host, Docker installation or storage layout.

The PostgreSQL data volume remains `growmaster_postgres`; automatic pre-restore copies use `growmaster_backups`.
