# Manual fertilization planning

The Planning screen includes **Gnojenje**, scoped to a bed and its recorded
plantings. This first increment records human decisions; it does not prescribe
crop doses, infer soil nutrient reserves, control fertigation, or change stock.

## Workflow

1. Select a bed. Review previous/current crops, recorded harvested mass, soil
   tests and actual applications. Missing harvest records are not evidence of
   zero nutrient removal. Crop residues and professional assumptions belong in
   the notes/rationale; no mineralization credit is inferred.
2. Enter soil results with sample date, sampled area, report source, method and
   the exact P/K unit and chemical form from the report. Results are retained as
   history; they are not automatically classified or converted between methods.
   A new test does not certify that older tests are representative or current.
3. Record each planned application for an active planting: date, treated area,
   product mass in kg, optional declared N/P2O5/K2O mass percentages and their
   source. Explain the dose and assumptions. Several applications can be planned
   separately. Products with unknown composition remain unknown, never zero.
4. Explicitly confirm the reviewed draft with the reviewer's name. This is a
   user-supplied name, not a verified agronomist identity. The saved context
   contains bed area, crop history, harvests, analyses and actual applications.
5. Only **Zabeleži izvedbo te količine** creates an actual record. Enter the real
   application date. If the amount differs, cancel the plan and record the actual
   amount separately. Changed context blocks confirmation/completion: review it
   and create a new plan. Executing one planned application thus requires review
   of remaining applications against the updated history.
6. Correct a mistaken actual record by voiding it with a reason, then entering
   the corrected record. Voided records remain visible and are excluded from
   totals. Voiding an application does not reopen its already completed plan.

Totals cover all recorded years and only non-voided **actual** applications.
They express declared kilograms of N, P2O5 and K2O, not plant-available nutrients
or a fertilizer recommendation. Each nutrient includes a count of entries with
unknown composition. Soil-test P/K values are never added to these totals.
Compost availability, prior-crop credits, expected crop requirements and soil
sufficiency need locally appropriate expert guidance before a dose is entered.
Liquid products require measured mass or a documented density conversion first.

## API and storage

All routes use `/api/fertilization` and existing authenticated/licensed server
middleware. Bed/planting/record lookups are farm-scoped, following the existing
single-farm convention. No network or hardware calls are made.

- `GET /beds/{id}`: history, totals, context version and plans; read-only.
- `POST /beds/{id}/soil-tests`: dated laboratory results.
- `POST /beds/{id}/applications`: actual manual application, no future dates.
- `POST /beds/{id}/plans`: draft with current context version and rationale.
- `POST /plans/{id}/confirm`: reviewer and current context version.
- `POST /plans/{id}/complete`: actual date; conditional transition and unique
  plan/application link prevent a second completion from duplicating the dose.
- `POST /plans/{id}/cancel`: cancel draft/confirmed plan.
- `POST /applications/{id}/void`: retain a mistaken record with its reason.

Migration `0020_fertilization` creates three additive tables. Portable backups
include these tables; older backups without them restore empty fertilization
records. There are no new dependencies, environment settings or services.

Validation covers lifecycle, non-counting of drafts, unknown composition,
invalid dates/areas/composition, farm scope, stale context, duplicate completion,
new planting continuity, repeatable migration and backup compatibility.
