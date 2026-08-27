"""Bridge structured baby-leaf recipes with GrowMaster supply/seed inventory."""

from __future__ import annotations

from dataclasses import dataclass

from app.mix_recipes import calculate_mix_seed_requirements


@dataclass(frozen=True)
class SeedStock:
    id: int
    name: str
    stock_g: float


def normalize_seed_name(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def match_seed_stock(crop: str, inventory: list[SeedStock]) -> SeedStock | None:
    """Match a recipe crop to a seed stock item without silently using another crop."""
    target = normalize_seed_name(crop)
    exact = [item for item in inventory if normalize_seed_name(item.name) == target]
    if len(exact) == 1:
        return exact[0]
    prefixed = [
        item for item in inventory
        if normalize_seed_name(item.name).startswith(target + " ")
        or normalize_seed_name(item.name).startswith("seme " + target)
    ]
    return prefixed[0] if len(prefixed) == 1 else None


def plan_mix_against_inventory(
    recipe_id: str,
    width_m: float,
    length_m: float,
    seed_rates_g_m2: dict[str, float],
    inventory: list[SeedStock],
    reserve_pct: float = 5.0,
):
    """Calculate a recipe and show stock availability for every component.

    Nothing is deducted here. This is the safe preview/reservation check shown
    before the user confirms sowing.
    """
    plan = calculate_mix_seed_requirements(
        recipe_id, width_m, length_m, seed_rates_g_m2, reserve_pct
    )
    shortages = []
    unmatched = []
    components = []
    for component in plan["components"]:
        required = component["required_seed_g"]
        stock = match_seed_stock(component["crop"], inventory)
        available = stock.stock_g if stock else None
        enough = bool(stock and required is not None and available >= required)
        shortage = None
        if stock is None:
            unmatched.append(component["crop"])
        elif required is not None and available < required:
            shortage = round(required - available, 2)
            shortages.append({"crop": component["crop"], "shortage_g": shortage})
        components.append({
            **component,
            "supply_item_id": stock.id if stock else None,
            "inventory_name": stock.name if stock else None,
            "available_seed_g": round(available, 2) if available is not None else None,
            "enough_stock": enough,
            "shortage_g": shortage,
        })
    return {
        **plan,
        "components": components,
        "unmatched_inventory_components": unmatched,
        "shortages": shortages,
        "inventory_ready": plan["ready"] and not unmatched and not shortages,
    }


def consume_mix_seed(plan: dict, stock_by_id: dict[int, float]) -> dict[int, float]:
    """Atomically validate then return new gram balances for a confirmed sowing.

    Caller persists the returned balances and creates SupplyUsage rows in the
    same database transaction. Validation happens before any balance changes.
    """
    if not plan.get("inventory_ready"):
        raise ValueError("Mešanice ni mogoče knjižiti: zaloga semen ni pripravljena.")
    deductions: dict[int, float] = {}
    for component in plan["components"]:
        item_id = component.get("supply_item_id")
        required = component.get("required_seed_g")
        if item_id is None or required is None:
            raise ValueError("Komponenta nima povezane zaloge ali količine semena.")
        deductions[item_id] = deductions.get(item_id, 0.0) + float(required)
    new_balances = dict(stock_by_id)
    for item_id, required in deductions.items():
        available = float(new_balances.get(item_id, 0.0))
        if available + 1e-9 < required:
            raise ValueError(f"Premalo semena v zalogi za supply_item_id={item_id}.")
        new_balances[item_id] = round(available - required, 3)
    return new_balances
