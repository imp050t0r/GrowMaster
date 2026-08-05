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

GitHub Actions compiles the backend, runs the complete farm-to-season-plan, multi-item direct-sale/price-list, invoice/PDF/credit-note/refund, sales-report, receivables, cash-flow, immutable daily-closing, supplier-purchasing, material-usage and supplier-payment API workflow test and builds the production frontend.

Operational and fiscal limitations of the invoice module are documented in [docs/invoices.md](docs/invoices.md).
