# Android, iPhone and synchronization

GrowMaster has one React user interface for the browser, installable PWA, Android and iPhone containers. This keeps field and desktop behavior consistent.

## PWA

The production frontend includes a manifest, Apple touch icon and a service worker. The service worker caches only the application shell and static assets; it deliberately never caches authenticated API responses containing farm, customer or financial data. On iPhone, open the HTTPS GrowMaster address in Safari and choose **Add to Home Screen**. On supported desktop and Android browsers, use **Install application**.

## Native apps

Capacitor wraps the same compiled frontend. On first launch, the user enters the private GrowMaster server URL. Native requests identify themselves with `X-GrowMaster-Client: mobile` and use a revocable 30-day bearer session. Browser clients continue using an HTTP-only, same-site cookie and never receive the bearer token.

The platform workflow publishes an Android debug APK for private testing. A Play Store release requires a protected Android signing key. The iPhone project is compiled without distribution signing in CI; installation outside the PWA requires an Apple Developer account, signing certificate and App Store/TestFlight provisioning.

The server allows only the explicit local Capacitor origins by default. A public deployment must use HTTPS and should set `CORS_ORIGINS` to the exact origins that are needed.

## Synchronization model

Desktop and phone do not exchange database files. They send validated operations to the same FastAPI server and PostgreSQL database, so saved changes are immediately visible to every signed-in device. Existing database transactions and stock checks remain the source of truth. Each installation still represents one farm; sharing a server between unrelated farms is not supported.

The current mobile release requires a connection when saving. The PWA shell remains visible offline, but API data is not cached and writes are not queued, avoiding silent duplicate harvests, sales or stock movements. A future offline queue must add idempotency keys and per-record conflict handling before it is safe for financial and inventory operations.

For local-network use the computer must be running and reachable, for example at `http://192.168.1.20:3000`. For use from anywhere, deploy the same Docker stack behind a private HTTPS reverse proxy; never expose PostgreSQL or the FastAPI port directly.

## HTTPS synchronization server

`docker-compose.remote.yml` adds Caddy in front of GrowMaster, removes the direct frontend port and obtains/renews a trusted TLS certificate for `GROWMASTER_DOMAIN`. Copy `.env.remote.example` to a private environment file, set a real domain and strong matching PostgreSQL password, point DNS to the server, allow inbound ports 80 and 443, then run:

```bash
docker compose --env-file .env.remote -f docker-compose.yml -f docker-compose.remote.yml up --build -d
```

The phone connects to `https://<GROWMASTER_DOMAIN>`. The database and FastAPI remain internal to Docker. Do not use this public-server overlay without operating-system updates, firewall rules, monitored backups and a trusted administrator.
