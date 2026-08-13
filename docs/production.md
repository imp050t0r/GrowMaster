# Production startup

GrowMaster's default Docker deployment is designed for one farm on a trusted local computer or private local network. The browser talks only to the Nginx frontend on port 3000. Nginx serves the compiled React application and forwards `/api` requests to FastAPI inside Docker; PostgreSQL and FastAPI are not exposed directly on the host.

## First start

1. Copy `.env.example` to `.env`.
2. Replace `change-me` with one long random database password in both `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL`. The two values must match.
3. Run `docker compose up --build -d`.
4. Open `http://localhost:3000` and complete the first administrator setup.
5. Open **Podatki** and confirm that **Pripravljeno za delo** is shown.
6. Download the first daily backup and keep a copy on another disk or trusted private storage.

Use `docker compose ps` to confirm that database, backend and frontend are all healthy. The services restart automatically after a Docker or computer restart unless the stack was deliberately stopped.

## Readiness checks

The authenticated `GET /api/system/readiness` endpoint and the **Podatki** screen verify:

- database connectivity,
- the current schema revision,
- write access to the persistent backup volume,
- checksum and age of the latest daily backup,
- administrator setup,
- a real farm name instead of the demo identity.

Tax number and seller address are a separate optional check. They do not block ordinary farm work or sales to final consumers, but must be completed before the first invoice to a legal entity.

## Safe operation

- Do not expose port 3000 directly to the public internet. Use a private network or a properly configured HTTPS reverse proxy.
- With plain local HTTP, keep `COOKIE_SECURE=false`. Set it to `true` only when the browser reaches GrowMaster through HTTPS.
- Keep `.env` private and never commit it.
- Keep at least one recent backup outside the Docker host.
- Before upgrading, download a backup, pull the new code, and run `docker compose up --build -d` again.

To stop the application without deleting data, use `docker compose stop`. Never add `--volumes` to a shutdown command unless the PostgreSQL and backup volumes are intentionally being destroyed.
