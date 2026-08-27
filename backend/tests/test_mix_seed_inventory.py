import json

import pytest

from app.mix_seed_inventory import consume_mix_from_inventory, plan_mix_against_inventory
from app.seed_inventory_service import load_inventory, save_inventory


def rates():
    return {
        "Mizuna": 2.0,
        "Tatsoi": 2.0,
        "Pak choi": 2.0,
        "Rdeča gorčica": 2.0,
        "Baby leaf regrat": 0.65,
    }


def payload(stock=100.0):
    names = ["Mizuna", "Tatsoi", "Pak choi", "Rdeča gorčica", "Baby leaf regrat"]
    return {
        "schema_version": 1,
        "next_id": 6,
        "lots": [
            {
                "id": i + 1,
                "crop": name,
                "variety": None,
                "unit": "g",
                "quantity": stock,
                "thousand_seed_weight_g": None,
                "purchase_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
            for i, name in enumerate(names)
        ],
        "transactions": [],
    }


def test_recipe_checks_each_real_inventory_component():
    plan = plan_mix_against_inventory(
        "asian_balanced_v1", 0.8, 15, rates(), payload=payload()
    )
    assert plan["inventory_ready"] is True
    assert len(plan["components"]) == 5
    assert all(c["allocation"] for c in plan["components"])
    assert all(c["enough_stock"] for c in plan["components"])


def test_recipe_reports_missing_and_short_seed_stock():
    data = payload()
    data["lots"] = [lot for lot in data["lots"] if lot["crop"] != "Tatsoi"]
    data["lots"][0]["quantity"] = 0.1
    plan = plan_mix_against_inventory(
        "asian_balanced_v1", 0.8, 15, rates(), payload=data
    )
    assert plan["inventory_ready"] is False
    assert any(row["crop"] == "Mizuna" for row in plan["shortages"])
    assert any(row["crop"] == "Tatsoi" for row in plan["shortages"])


def test_confirmed_mix_atomically_deducts_lots_and_records_transactions(tmp_path, monkeypatch):
    inventory_file = tmp_path / "seed.json"
    monkeypatch.setenv("GROWMASTER_SEED_INVENTORY_FILE", str(inventory_file))
    save_inventory(payload())

    result = consume_mix_from_inventory(
        "asian_balanced_v1", 0.8, 15, rates(), reference="bed-A1-2026-08-27"
    )
    saved = load_inventory()
    assert result["committed"] is True
    assert result["transactions_created"] == 5
    assert len(saved["transactions"]) == 5
    assert all(tx["reason"] == "baby_leaf_mix_sowing" for tx in saved["transactions"])
    assert all(tx["reference"] == "bed-A1-2026-08-27" for tx in saved["transactions"])
    for component in result["components"]:
        lot_id = component["allocation"][0]["lot_id"]
        lot = next(row for row in saved["lots"] if row["id"] == lot_id)
        assert lot["quantity"] == pytest.approx(
            100.0 - component["required_seed_g"], abs=0.001
        )


def test_gram_requirement_can_consume_seed_count_lot_when_tkw_exists():
    data = payload()
    mizuna = data["lots"][0]
    mizuna["unit"] = "seeds"
    mizuna["quantity"] = 100000
    mizuna["thousand_seed_weight_g"] = 2.0
    plan = plan_mix_against_inventory(
        "asian_balanced_v1", 0.8, 15, rates(), payload=data
    )
    mizuna_component = next(c for c in plan["components"] if c["crop"] == "Mizuna")
    assert mizuna_component["enough_stock"] is True
    assert mizuna_component["allocation"][0]["lot_unit"] == "seeds"


def test_unconvertible_seed_count_lot_is_not_guessed():
    data = payload()
    mizuna = data["lots"][0]
    mizuna["unit"] = "seeds"
    mizuna["quantity"] = 100000
    mizuna["thousand_seed_weight_g"] = None
    plan = plan_mix_against_inventory(
        "asian_balanced_v1", 0.8, 15, rates(), payload=data
    )
    mizuna_component = next(c for c in plan["components"] if c["crop"] == "Mizuna")
    assert mizuna_component["enough_stock"] is False
    assert mizuna_component["unconvertible_lot_ids"] == [1]
