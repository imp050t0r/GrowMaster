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
- harvest records with quantity, quality and remaining sellable stock
- costs, sales and automatic profit per bed
- live inventory with sold, reserved and available harvest quantities
- customers and orders with stock reservation, fulfilment and cancellation
- customer types for final consumers and business entities
- quick market and farm-gate sales with anonymous final-consumer checkout
- configurable Article 81.a basic-agriculture invoice exemption
- printable internal sale confirmations, delivery notes and business invoices
- seasonal crop plans with succession sowings and activation into field work
- calendar for sowing, transplanting, harvest, tasks and deliveries
- crop forecast comparing current stock, planned yield and confirmed demand
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

GitHub Actions compiles the backend, runs the complete farm-to-season-plan and direct-sale API workflow test and builds the production frontend.
