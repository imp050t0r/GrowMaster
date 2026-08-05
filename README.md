# GrowMaster

GrowMaster is a local-first farm management application for professional market gardens.

## Current MVP

- crop library with multiple varieties per crop
- mobile dashboard with today's work, active beds and next harvest
- bed creation, occupancy status, detail view and crop history
- sowing form: crop, variety, date and bed
- automatic assignment of a sowing to the selected bed
- crop-rotation warning with an explicit user override
- three automatic follow-up tasks for every sowing
- daily task center with date, priority, bed, duration, material use and notes
- completion of a crop cycle releases the bed and updates rotation history
- PostgreSQL, FastAPI and React/Vite in Docker Compose

## Start

```bash
cp .env.example .env
docker compose up --build
```

Open:

- application: http://localhost:3000
- API documentation: http://localhost:8000/docs
- API health: http://localhost:8000/api/health

## Core rule

GrowMaster may recommend and warn, but the user makes the final decision. A rotation warning can only be overridden explicitly by the user.

## Validation

GitHub Actions compiles the backend, runs the complete bed/planting/task API workflow test and builds the production frontend.
