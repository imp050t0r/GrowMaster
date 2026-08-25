from __future__ import annotations

import math

import pytest

from app.seed_inventory_service import (
    adjust_lot,
    convert_quantity,
    create_lot,
    load_inventory,
    purchase_recommendation,
    requirement_from_target_plants,
    stock_summary,
)


@pytest.fixture()
def inventory_file(tmp_path, monkeypatch):
    path = tmp_path / "seed-inventory.json"
    monkeypatch.setenv("GROWMASTER_SEED_INVENTORY_FILE", str(path))
    return path


def test_grams_seed_conversion_uses_tkw():
    assert convert_quantity(2.0, "g", "seeds", 2.0) == pytest.approx(1000)
    assert convert_quantity(1000, "seeds", "g", 2.0) == pytest.approx(2.0)


def test_grams_seed_conversion_requires_tkw():
    with pytest.raises(ValueError):
        convert_quantity(10, "g", "seeds", None)


def test_seed_and_pellet_counts_are_equivalent():
    assert convert_quantity(2500, "pellets", "seeds", None) == pytest.approx(2500)


def test_inventory_adjustment_records_transaction_and_prevents_negative(inventory_file):
    lot = create_lot({"crop": "Solata", "variety": "Salanova", "unit": "pellets", "quantity": 10000, "package_size": 5000})
    updated = adjust_lot(lot["id"], -2500, "pellets", "Setev A1", "planting:1")
    assert updated["quantity"] == pytest.approx(7500)
    payload = load_inventory()
    assert payload["transactions"][-1]["reference"] == "planting:1"
    with pytest.raises(ValueError):
        adjust_lot(lot["id"], -8000, "pellets", "Preveč", "planting:2")
    assert load_inventory()["lots"][0]["quantity"] == pytest.approx(7500)


def test_stock_summary_converts_multiple_lots(inventory_file):
    create_lot({"crop": "Rukola", "variety": "Astro", "unit": "g", "quantity": 20, "thousand_seed_weight_g": 2.0})
    create_lot({"crop": "Rukola", "variety": "Astro", "unit": "seeds", "quantity": 5000, "thousand_seed_weight_g": 2.0})
    summary = stock_summary("Rukola", "Astro", "g")
    assert summary["quantity"] == pytest.approx(30.0)
    assert summary["convertible_lots"] == 2


def test_plant_requirement_accounts_for_germination_emergence_and_reserve():
    required = requirement_from_target_plants(10000, 95, 90, 5)
    assert required == math.ceil(10000 / 0.95 / 0.90 * 1.05)


def test_purchase_recommendation_rounds_to_whole_packages():
    result = purchase_recommendation(12281, "seeds", 4000, 5000)
    assert result["status"] == "ORDER"
    assert result["packages_to_order"] == 2
    assert result["order_quantity"] == pytest.approx(10000)


def test_purchase_recommendation_is_ok_when_stock_is_enough():
    result = purchase_recommendation(5000, "pellets", 7000, 5000)
    assert result["status"] == "OK"
    assert result["packages_to_order"] == 0
