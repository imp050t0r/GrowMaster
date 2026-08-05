import os
from pathlib import Path

TEST_DATABASE = Path("growmaster-test.db")
TEST_DATABASE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DATABASE}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_bed_planting_and_task_workflow() -> None:
    with TestClient(app) as client:
        beds = client.get("/api/beds").json()
        crops = client.get("/api/crops").json()
        assert len(beds) == 6
        assert crops

        new_bed = client.post(
            "/api/beds",
            json={"name": "B1", "width_m": 0.8, "length_m": 15},
        )
        assert new_bed.status_code == 201
        assert new_bed.json()["area_m2"] == 12.0

        crop = next(item for item in crops if item["name"] == "Rukola")
        variety = next(item for item in crop["varieties"] if item["name"] == "Astro")
        bed = next(item for item in beds if item["name"] == "A3")
        planting = client.post(
            "/api/plantings",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "bed_id": bed["id"],
                "sowing_date": "2026-08-05",
            },
        )
        assert planting.status_code == 201
        assert "tri opravila" in planting.json()["message"]

        detail = client.get(f"/api/beds/{bed['id']}")
        assert detail.status_code == 200
        assert detail.json()["current_planting"]["variety"] == "Astro"
        planting_tasks = [
            item
            for item in detail.json()["tasks"]
            if item["planting_id"] == planting.json()["id"]
        ]
        assert len(planting_tasks) == 3

        task = planting_tasks[0]
        completed = client.post(
            f"/api/tasks/{task['id']}/complete",
            json={
                "duration_minutes": 25,
                "quantity_used": 120,
                "unit": "L",
                "notes": "Pregled in zalivanje zaključena.",
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["duration_minutes"] == 25

        finished = client.post(f"/api/plantings/{planting.json()['id']}/finish")
        assert finished.status_code == 200
        refreshed_bed = client.get(f"/api/beds/{bed['id']}").json()
        assert refreshed_bed["status"] == "empty"
        assert refreshed_bed["last_crop_family"] == "Brassicaceae"

        harvest = client.post(
            "/api/harvests",
            json={
                "planting_id": planting.json()["id"],
                "harvest_date": "2026-09-10",
                "quantity_kg": 18.5,
                "quality": "A",
                "notes": "Prva kakovost.",
            },
        )
        assert harvest.status_code == 201
        assert harvest.json()["available_kg"] == 18.5

        cost = client.post(
            "/api/costs",
            json={
                "bed_id": bed["id"],
                "planting_id": planting.json()["id"],
                "cost_date": "2026-09-09",
                "category": "labor",
                "amount_eur": 42.5,
                "description": "Pobiranje in pakiranje",
            },
        )
        assert cost.status_code == 201

        sale = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 15,
                "price_per_kg_eur": 6,
                "customer": "Tržnica",
            },
        )
        assert sale.status_code == 201
        assert sale.json()["revenue_eur"] == 90

        oversold = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 4,
                "price_per_kg_eur": 6,
            },
        )
        assert oversold.status_code == 409

        harvest_summary = client.get("/api/harvests").json()[0]
        assert harvest_summary["sold_kg"] == 15
        assert harvest_summary["available_kg"] == 3.5

        economics = client.get("/api/economics/by-bed").json()
        bed_economics = next(item for item in economics if item["bed_id"] == bed["id"])
        assert bed_economics["harvested_kg"] == 18.5
        assert bed_economics["costs_eur"] == 42.5
        assert bed_economics["revenue_eur"] == 90
        assert bed_economics["profit_eur"] == 47.5

        customer = client.post(
            "/api/customers",
            json={
                "name": "Bistro Zeleno",
                "email": "narocila@example.com",
                "phone": "+386 40 000 000",
                "address": "Tržna ulica 1, Ljubljana",
                "customer_type": "business",
                "tax_number": "SI12345678",
            },
        )
        assert customer.status_code == 201

        inventory = client.get("/api/inventory").json()
        stock = next(item for item in inventory if item["harvest_id"] == harvest.json()["id"])
        assert stock["available_kg"] == 3.5
        assert stock["reserved_kg"] == 0

        reserved_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-10",
                "delivery_date": "2026-09-11",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 3,
                        "price_per_kg_eur": 6.5,
                    }
                ],
            },
        )
        assert reserved_order.status_code == 201
        assert reserved_order.json()["status"] == "confirmed"
        assert reserved_order.json()["total_eur"] == 19.5

        reserved_stock = client.get("/api/inventory").json()
        reserved_stock = next(
            item for item in reserved_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert reserved_stock["reserved_kg"] == 3
        assert reserved_stock["available_kg"] == 0.5

        sale_into_reservation = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 1,
                "price_per_kg_eur": 6,
            },
        )
        assert sale_into_reservation.status_code == 409

        unavailable_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-10",
                "delivery_date": "2026-09-11",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 1,
                        "price_per_kg_eur": 6.5,
                    }
                ],
            },
        )
        assert unavailable_order.status_code == 409

        delivery_note = client.get(
            f"/api/orders/{reserved_order.json()['id']}/document?document_type=delivery_note"
        )
        assert delivery_note.status_code == 200
        assert delivery_note.json()["document_number"].startswith("D-")

        cancelled = client.post(
            f"/api/orders/{reserved_order.json()['id']}/status",
            json={"status": "cancelled"},
        )
        assert cancelled.status_code == 200
        released_stock = client.get("/api/inventory").json()
        released_stock = next(
            item for item in released_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert released_stock["available_kg"] == 3.5

        fulfilled_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-11",
                "delivery_date": "2026-09-12",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 2,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert fulfilled_order.status_code == 201
        fulfilled = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/status",
            json={"status": "fulfilled"},
        )
        assert fulfilled.status_code == 200
        invoice = client.get(
            f"/api/orders/{fulfilled_order.json()['id']}/document?document_type=invoice"
        )
        assert invoice.status_code == 410

        sales_identity = client.put(
            "/api/sales-settings",
            json={
                "basic_agriculture_invoice_exemption": True,
                "seller_name": "Kmetija Zeleni Gaj",
                "seller_tax_number": "SI87654321",
            },
        )
        assert sales_identity.status_code == 200
        invoice_profile = client.put(
            "/api/invoice-profile",
            json={
                "seller_address": "Poljska pot 5, 1000 Ljubljana",
                "seller_iban": "SI56191000000123456",
                "seller_registration_number": "1234567000",
                "vat_note": "DDV ni obračunan v skladu s posebnim režimom.",
                "business_premise_code": "GM",
                "device_code": "01",
                "default_due_days": 14,
            },
        )
        assert invoice_profile.status_code == 200
        archived_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "order",
                "source_id": fulfilled_order.json()["id"],
                "issued_on": "2026-09-12",
                "payment_method": "bank_transfer",
            },
        )
        assert archived_invoice.status_code == 201
        archived_invoice_data = archived_invoice.json()
        assert archived_invoice_data["number"] == "R-GM-01-2026-0001"
        assert archived_invoice_data["due_date"] == "2026-09-26"
        assert archived_invoice_data["fiscal_status"] == "not_required"
        assert archived_invoice_data["customer"]["tax_number"] == "SI12345678"
        assert archived_invoice_data["lines"][0]["line_total_eur"] == 14
        assert len(archived_invoice_data["pdf_sha256"]) == 64
        invoice_pdf = client.get(
            f"/api/invoices/{archived_invoice_data['id']}/pdf"
        )
        assert invoice_pdf.status_code == 200
        assert invoice_pdf.headers["content-type"] == "application/pdf"
        assert invoice_pdf.content.startswith(b"%PDF")
        assert client.get(
            f"/api/invoices/{archived_invoice_data['id']}/pdf"
        ).content == invoice_pdf.content
        duplicate_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "order",
                "source_id": fulfilled_order.json()["id"],
                "issued_on": "2026-09-13",
            },
        )
        assert duplicate_invoice.status_code == 409

        final_stock = client.get("/api/inventory").json()
        final_stock = next(
            item for item in final_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert final_stock["sold_kg"] == 17
        assert final_stock["reserved_kg"] == 0
        assert final_stock["available_kg"] == 1.5

        future_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-15",
                "delivery_date": "2026-09-25",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 1,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert future_order.status_code == 201

        plan_series = client.post(
            "/api/plans",
            json={
                "bed_id": bed["id"],
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-09-20",
                "transplant_date": "2026-09-27",
                "expected_yield_kg": 8,
                "succession_count": 2,
                "succession_interval_days": 14,
                "notes": "Jesenska zaporedna setev",
            },
        )
        assert plan_series.status_code == 201
        assert len(plan_series.json()["plans"]) == 2
        assert plan_series.json()["warnings"]

        calendar = client.get(
            "/api/planning/calendar?start=2026-09-20&end=2026-11-30"
        )
        assert calendar.status_code == 200
        event_types = {event["type"] for event in calendar.json()["events"]}
        assert {"sowing", "transplant", "planned_harvest", "delivery"} <= event_types

        forecast = client.get(
            "/api/planning/forecast?start=2026-09-20&end=2026-11-30"
        )
        assert forecast.status_code == 200
        crop_forecast = next(
            item for item in forecast.json()["rows"] if item["crop_id"] == crop["id"]
        )
        assert crop_forecast["current_stock_kg"] == 1.5
        assert crop_forecast["planned_yield_kg"] == 16
        assert crop_forecast["confirmed_demand_kg"] == 1
        assert crop_forecast["projected_balance_kg"] == 16.5

        first_plan, second_plan = plan_series.json()["plans"]
        rotation_blocked = client.post(
            f"/api/plans/{first_plan['id']}/activate",
            json={"override_rotation": False},
        )
        assert rotation_blocked.status_code == 409
        activated = client.post(
            f"/api/plans/{first_plan['id']}/activate",
            json={"override_rotation": True},
        )
        assert activated.status_code == 200
        assert activated.json()["plan"]["status"] == "activated"
        assert activated.json()["planting_id"]

        cancelled_plan = client.post(
            f"/api/plans/{second_plan['id']}/status",
            json={"status": "cancelled"},
        )
        assert cancelled_plan.status_code == 200
        visible_plans = client.get("/api/plans").json()
        assert len(visible_plans) == 1
        assert visible_plans[0]["status"] == "activated"

        settings = client.get("/api/sales-settings")
        assert settings.status_code == 200
        assert settings.json()["basic_agriculture_invoice_exemption"] is True

        anonymous_sale = client.post(
            "/api/retail-sales",
            json={
                "sale_date": "2026-09-20",
                "payment_method": "cash",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 0.4,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert anonymous_sale.status_code == 201
        assert anonymous_sale.json()["customer"] == "Končni potrošnik"
        assert anonymous_sale.json()["customer_type"] == "consumer"
        assert anonymous_sale.json()["invoice_required"] is False
        assert anonymous_sale.json()["total_eur"] == 2.8

        receipt = client.get(
            f"/api/retail-sales/{anonymous_sale.json()['id']}/document?document_type=receipt"
        )
        assert receipt.status_code == 200
        assert receipt.json()["document_number"].startswith("P-")
        consumer_invoice = client.get(
            f"/api/retail-sales/{anonymous_sale.json()['id']}/document?document_type=invoice"
        )
        assert consumer_invoice.status_code == 409

        business_sale = client.post(
            "/api/retail-sales",
            json={
                "customer_id": customer.json()["id"],
                "sale_date": "2026-09-20",
                "payment_method": "card",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 0.1,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert business_sale.status_code == 201
        assert business_sale.json()["customer_type"] == "business"
        assert business_sale.json()["invoice_required"] is True
        business_invoice = client.get(
            f"/api/retail-sales/{business_sale.json()['id']}/document?document_type=invoice"
        )
        assert business_invoice.status_code == 410

        fiscal_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "retail_sale",
                "source_id": business_sale.json()["id"],
                "issued_on": "2026-09-20",
            },
        )
        assert fiscal_invoice.status_code == 201
        fiscal_invoice_data = fiscal_invoice.json()
        assert fiscal_invoice_data["number"] == "R-GM-01-2026-0002"
        assert fiscal_invoice_data["fiscal_status"] == "pending"
        pending_pdf = client.get(
            f"/api/invoices/{fiscal_invoice_data['id']}/pdf"
        )
        assert pending_pdf.status_code == 409
        confirmation = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/fiscal-confirmation",
            json={"eor": "EOR-RAČUN-001", "zoi": "ZOI-RAČUN-001"},
        )
        assert confirmation.status_code == 200
        assert confirmation.json()["fiscal_status"] == "confirmed"
        assert len(confirmation.json()["pdf_sha256"]) == 64
        locked_confirmation = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/fiscal-confirmation",
            json={"eor": "DRUG-EOR"},
        )
        assert locked_confirmation.status_code == 409
        confirmed_pdf = client.get(
            f"/api/invoices/{fiscal_invoice_data['id']}/pdf"
        )
        assert confirmed_pdf.status_code == 200
        assert confirmed_pdf.content.startswith(b"%PDF")

        retail_stock = client.get("/api/inventory").json()
        retail_stock = next(
            item for item in retail_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert retail_stock["available_kg"] == 0

        sales_report = client.get(
            "/api/sales-report?start=2026-09-12&end=2026-09-20"
        )
        assert sales_report.status_code == 200
        report = sales_report.json()
        assert report["summary"] == {
            "transactions": 3,
            "total_eur": 17.5,
            "cash_eur": 2.8,
            "card_eur": 0.7,
            "bank_transfer_eur": 0,
            "invoice_eur": 14.7,
            "unclassified_eur": 0,
            "consumer_eur": 2.8,
            "business_eur": 14.7,
            "invoice_count": 2,
        }
        assert len(report["daily"]) == 2
        assert report["daily"][0]["date"] == "2026-09-20"
        assert {entry["source"] for entry in report["entries"]} == {
            "retail_sale",
            "order",
        }
        order_entry = next(
            entry for entry in report["entries"] if entry["source"] == "order"
        )
        assert order_entry["payment_method"] == "invoice"

        sales_csv = client.get(
            "/api/sales-report/export.csv?start=2026-09-12&end=2026-09-20"
        )
        assert sales_csv.status_code == 200
        assert sales_csv.headers["content-type"].startswith("text/csv")
        assert "GM-2026" in sales_csv.text
        assert "Končni potrošnik" in sales_csv.text

        invalid_report = client.get(
            "/api/sales-report?start=2026-09-21&end=2026-09-20"
        )
        assert invalid_report.status_code == 422

        before_delivery = client.get("/api/receivables?as_of=2026-09-11")
        assert before_delivery.status_code == 200
        assert before_delivery.json()["summary"]["invoice_count"] == 0
        assert before_delivery.json()["items"] == []

        overdue_receivables = client.get("/api/receivables?as_of=2026-09-27")
        assert overdue_receivables.status_code == 200
        assert overdue_receivables.json()["summary"] == {
            "invoice_count": 1,
            "open_count": 1,
            "overdue_count": 1,
            "invoiced_eur": 14,
            "paid_eur": 0,
            "outstanding_eur": 14,
            "overdue_eur": 14,
        }
        receivable = overdue_receivables.json()["items"][0]
        assert receivable["order_id"] == fulfilled_order.json()["id"]
        assert receivable["due_date"] == "2026-09-26"
        assert receivable["status"] == "overdue"
        assert receivable["days_overdue"] == 1

        partial_payment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-20",
                "amount_eur": 4,
                "payment_method": "bank_transfer",
                "notes": "Delno nakazilo",
            },
        )
        assert partial_payment.status_code == 201
        assert partial_payment.json()["status"] == "partial"
        assert partial_payment.json()["paid_eur"] == 4
        assert partial_payment.json()["outstanding_eur"] == 10

        overpayment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-21",
                "amount_eur": 11,
                "payment_method": "bank_transfer",
            },
        )
        assert overpayment.status_code == 409

        final_payment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-21",
                "amount_eur": 10,
                "payment_method": "bank_transfer",
            },
        )
        assert final_payment.status_code == 201
        assert final_payment.json()["status"] == "paid"
        assert final_payment.json()["outstanding_eur"] == 0
        assert len(final_payment.json()["payments"]) == 2

        historical_receivables = client.get(
            "/api/receivables?as_of=2026-09-20&include_paid=true"
        )
        historical = historical_receivables.json()["items"][0]
        assert historical["status"] == "partial"
        assert historical["paid_eur"] == 4
        assert historical["outstanding_eur"] == 10
        assert len(historical["payments"]) == 1

        open_receivables = client.get("/api/receivables?as_of=2026-09-27")
        assert open_receivables.status_code == 200
        assert open_receivables.json()["items"] == []
        assert open_receivables.json()["summary"]["paid_eur"] == 14
        assert open_receivables.json()["summary"]["outstanding_eur"] == 0

        paid_receivables = client.get(
            "/api/receivables?as_of=2026-09-27&include_paid=true"
        )
        assert len(paid_receivables.json()["items"]) == 1
        assert paid_receivables.json()["items"][0]["status"] == "paid"

        cash_flow = client.get(
            "/api/cash-flow?start=2026-09-09&end=2026-09-21"
        )
        assert cash_flow.status_code == 200
        flow = cash_flow.json()
        assert flow["summary"] == {
            "inflow_eur": 17.5,
            "outflow_eur": 42.5,
            "net_eur": -25,
            "inflow_count": 4,
            "outflow_count": 1,
            "refund_eur": 0,
            "refund_count": 0,
            "cash_eur": 2.8,
            "card_eur": 0.7,
            "bank_transfer_eur": 14,
            "costs_by_category": {"labor": 42.5},
        }
        assert len(flow["entries"]) == 5
        assert {entry["source"] for entry in flow["entries"]} == {
            "retail_sale",
            "order_payment",
            "cost",
        }
        assert [day["date"] for day in flow["daily"]] == [
            "2026-09-21",
            "2026-09-20",
            "2026-09-09",
        ]
        assert flow["daily"][0]["net_eur"] == 10
        assert flow["daily"][1]["inflow_eur"] == 7.5
        assert flow["daily"][2]["net_eur"] == -42.5

        cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2026-09-09&end=2026-09-21"
        )
        assert cash_flow_csv.status_code == 200
        assert cash_flow_csv.headers["content-type"].startswith("text/csv")
        assert "Plačilo računa" in cash_flow_csv.text
        assert "Pobiranje in pakiranje" in cash_flow_csv.text

        invalid_cash_flow = client.get(
            "/api/cash-flow?start=2026-09-22&end=2026-09-21"
        )
        assert invalid_cash_flow.status_code == 422

        credit_note = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/credit-notes",
            json={
                "issued_on": "2026-09-22",
                "reason": "Napačno evidentirana poslovna prodaja.",
            },
        )
        assert credit_note.status_code == 201
        credit_note_data = credit_note.json()
        assert credit_note_data["number"] == "DB-GM-01-2026-0001"
        assert credit_note_data["fiscal_status"] == "pending"
        assert credit_note_data["paid_eur"] == 0.7
        assert credit_note_data["refunded_eur"] == 0
        assert credit_note_data["refundable_eur"] == 0.7
        assert credit_note_data["refunds"] == []
        assert client.get(
            f"/api/credit-notes/{credit_note_data['id']}/pdf"
        ).status_code == 409
        pending_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.4,
                "payment_method": "card",
            },
        )
        assert pending_refund.status_code == 409
        credit_confirmation = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/fiscal-confirmation",
            json={"eor": "EOR-DOBROPIS-001", "zoi": "ZOI-DOBROPIS-001"},
        )
        assert credit_confirmation.status_code == 200
        assert len(credit_confirmation.json()["pdf_sha256"]) == 64
        credit_pdf = client.get(
            f"/api/credit-notes/{credit_note_data['id']}/pdf"
        )
        assert credit_pdf.status_code == 200
        assert credit_pdf.content.startswith(b"%PDF")

        partial_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.4,
                "payment_method": "card",
                "notes": "Delno vračilo",
            },
        )
        assert partial_refund.status_code == 201
        assert partial_refund.json()["credit_note"]["refunded_eur"] == 0.4
        assert partial_refund.json()["credit_note"]["refundable_eur"] == 0.3

        over_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.31,
                "payment_method": "card",
            },
        )
        assert over_refund.status_code == 409

        final_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.3,
                "payment_method": "card",
            },
        )
        assert final_refund.status_code == 201
        assert final_refund.json()["credit_note"]["refunded_eur"] == 0.7
        assert final_refund.json()["credit_note"]["refundable_eur"] == 0
        assert len(final_refund.json()["credit_note"]["refunds"]) == 2
        assert client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-24",
                "amount_eur": 0.01,
                "payment_method": "cash",
            },
        ).status_code == 409

        refund_cash_flow = client.get(
            "/api/cash-flow?start=2026-09-23&end=2026-09-23"
        )
        assert refund_cash_flow.status_code == 200
        refund_flow = refund_cash_flow.json()
        assert refund_flow["summary"] == {
            "inflow_eur": 0,
            "outflow_eur": 0.7,
            "net_eur": -0.7,
            "inflow_count": 0,
            "outflow_count": 2,
            "refund_eur": 0.7,
            "refund_count": 2,
            "cash_eur": 0,
            "card_eur": 0,
            "bank_transfer_eur": 0,
            "costs_by_category": {},
        }
        assert len(refund_flow["entries"]) == 2
        assert {entry["source"] for entry in refund_flow["entries"]} == {"refund"}
        assert {entry["method"] for entry in refund_flow["entries"]} == {"card"}
        assert {entry["reference"] for entry in refund_flow["entries"]} == {
            "DB-GM-01-2026-0001"
        }
        refund_cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2026-09-23&end=2026-09-23"
        )
        assert refund_cash_flow_csv.status_code == 200
        assert "Vračilo po dobropisu" in refund_cash_flow_csv.text
        assert "DB-GM-01-2026-0001" in refund_cash_flow_csv.text
        assert client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/credit-notes",
            json={"issued_on": "2026-09-23", "reason": "Drugi dobropis"},
        ).status_code == 409

        archived_documents = client.get("/api/invoices")
        assert archived_documents.status_code == 200
        assert len(archived_documents.json()) == 2
        credited = next(
            item for item in archived_documents.json()
            if item["id"] == fiscal_invoice_data["id"]
        )
        assert credited["status"] == "credited"
        assert credited["credit_note"]["number"] == "DB-GM-01-2026-0001"
        assert credited["credit_note"]["refunded_eur"] == 0.7
        assert credited["credit_note"]["refundable_eur"] == 0
        assert len(credited["credit_note"]["refunds"]) == 2
        assert invalid_cash_flow.status_code == 422
