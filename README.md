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
- workers and family/owner labor with reusable hourly rates
- automatic labor-cost entry when a daily task is completed by a selected worker
- manual labor entries for work outside the task list, with optional bed and planting allocation
- date-filtered labor report by worker and bed, including unallocated hours
- completion of a crop cycle releases the bed and updates rotation history
- harvest records with quantity, quality and remaining sellable stock
- direct, material and labor costs with automatic profit per bed
- live inventory with sold, reserved and available harvest quantities
- customers and orders with stock reservation, fulfilment and cancellation
- customer types for final consumers and business entities
- quick market and farm-gate sales with anonymous final-consumer checkout
- multi-item market basket with live totals and stock validation
- reusable price list by crop and produce quality with automatic price suggestions
- configurable Article 81.a basic-agriculture invoice exemption
- printable internal sale confirmations and delivery notes
- immutable business invoices with yearly sequential numbering and seller/customer snapshots
- archived PDF invoices, configurable due dates and links to receivables and payments
- EOR/ZOI recording for cash or card invoices before the final PDF is released
- immutable full credit notes that preserve the original invoice history
- partial or full refund records linked to confirmed credit notes
- safeguards against refunding more than the customer actually paid
- date-filtered sales register with daily totals by payment method
- separate totals for final consumers, business customers and issued invoices
- semicolon-delimited UTF-8 CSV sales export for spreadsheet use
- open and overdue receivables for invoiced orders with a 14-day due date
- partial and final payment records with cash, card or bank-transfer method
- payment history and outstanding balance per business invoice
- actual cash-flow view combining paid direct sales, received invoice payments and refunds
- separate cost and refund outflows, daily net movement and payment-method breakdown
- date-filtered UTF-8 CSV cash-flow export
- daily sales closing with cash, card, bank-transfer and refund control totals
- opening, expected and counted cash with an automatic drawer difference
- immutable daily-close history that locks later money entries for a closed date
- supplier directory with tax and contact details
- seed, fertilizer, packaging, tool and other supply inventory with reorder warnings
- multi-item purchase orders with expected delivery, payment method and total cost
- full-order receipt that updates supply stock and prevents duplicate receipt
- cancellation of purchase orders that have not yet been received
- material usage by bed and optional planting with automatic stock reduction
- weighted-average material valuation from received purchases or a manual opening-stock cost
- separate direct and material costs in the automatic profit calculation per bed
- date-filtered seasonal profitability by bed and crop
- gross and net revenue after credit notes, with direct, material and labor cost breakdowns
- margin, yield per square metre, revenue and profit per square metre, and profit per labor hour
- explicit visibility of costs that are not allocated to a planting
- general farm expenses for fuel, utilities, rent, insurance, maintenance and administration
- cash, card and bank-transfer tracking for general expenses without assigning an artificial bed
- general expenses included in profitability, cash flow and immutable daily closing
- automatic database schema revisions that safely adopt existing installations
- portable full-data backups with schema version, record counts and SHA-256 verification
- transactional restore with automatic pre-restore recovery copies and sequence repair
- separate persistent Docker volume retaining the ten newest recovery copies
- first-use administrator setup with a locally hashed password
- HTTP-only, 30-day local sessions, logout and protection of every business-data API
- in-app display-name and password changes with current-password confirmation
- immediate revocation of every older browser session after a password change
- portable backups that deliberately exclude passwords and active sessions
- semicolon-delimited UTF-8 CSV profitability export
- partial and final supplier payments with payment history and overpayment safeguards
- supplier-payment outflows in cash flow and immutable daily sales closing
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

GitHub Actions compiles the backend, runs the complete farm-to-season-plan, task/labor-cost, multi-item direct-sale/price-list, invoice/PDF/credit-note/refund, sales-report, receivables, cash-flow, immutable daily-closing, supplier-purchasing, material-usage, supplier-payment, general-farm-expense, seasonal-profitability and full backup/restore API workflow test and builds the production frontend.

Operational and fiscal limitations of the invoice module are documented in [docs/invoices.md](docs/invoices.md).
Database upgrades, portable backups and recovery behavior are documented in [docs/data-safety.md](docs/data-safety.md).
Local password setup, sessions and deployment guidance are documented in [docs/authentication.md](docs/authentication.md).
