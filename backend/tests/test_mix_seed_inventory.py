import pytest

from app.mix_seed_inventory import SeedStock, consume_mix_seed, plan_mix_against_inventory


def rates():
    return {
        "Mizuna": 2.0,
        "Tatsoi": 2.0,
        "Pak choi": 2.0,
        "Rdeča gorčica": 2.0,
        "Baby leaf regrat": 0.65,
    }


def inventory(stock=100.0):
    names = ["Mizuna", "Tatsoi", "Pak choi", "Rdeča gorčica", "Baby leaf regrat"]
    return [SeedStock(i + 1, name, stock) for i, name in enumerate(names)]


def test_recipe_checks_each_seed_inventory_component():
    plan = plan_mix_against_inventory("asian_balanced_v1", 0.8, 15, rates(), inventory())
    assert plan["inventory_ready"] is True
    assert len(plan["components"]) == 5
    assert all(c["supply_item_id"] for c in plan["components"])
    assert all(c["enough_stock"] for c in plan["components"])


def test_recipe_reports_missing_and_short_seed_stock():
    stock = inventory()
    stock = [item for item in stock if item.name != "Tatsoi"]
    stock[0] = SeedStock(stock[0].id, stock[0].name, 0.1)
    plan = plan_mix_against_inventory("asian_balanced_v1", 0.8, 15, rates(), stock)
    assert plan["inventory_ready"] is False
    assert "Tatsoi" in plan["unmatched_inventory_components"]
    assert any(row["crop"] == "Mizuna" for row in plan["shortages"])


def test_confirmed_mix_deducts_all_components_only_after_validation():
    plan = plan_mix_against_inventory("asian_balanced_v1", 0.8, 15, rates(), inventory())
    balances = {item.id: item.stock_g for item in inventory()}
    updated = consume_mix_seed(plan, balances)
    for component in plan["components"]:
        item_id = component["supply_item_id"]
        assert updated[item_id] == pytest.approx(
            balances[item_id] - component["required_seed_g"], abs=0.001
        )


def test_consume_refuses_stale_insufficient_balance():
    plan = plan_mix_against_inventory("asian_balanced_v1", 0.8, 15, rates(), inventory())
    balances = {item.id: item.stock_g for item in inventory()}
    balances[1] = 0
    with pytest.raises(ValueError):
        consume_mix_seed(plan, balances)
