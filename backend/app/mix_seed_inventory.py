"""Bridge structured baby-leaf recipes with GrowMaster Seed Inventory lots."""

from __future__ import annotations

from datetime import datetime

from app.mix_recipes import calculate_mix_seed_requirements
from app.seed_inventory_service import convert_quantity, load_inventory, save_inventory


def _matching_lots(payload: dict, crop: str) -> list[dict]:
    return [
        lot for lot in payload.get("lots", [])
        if str(lot.get("crop") or "").casefold() == crop.casefold()
        and float(lot.get("quantity") or 0) > 0
    ]


def _available_grams(lot: dict) -> float | None:
    try:
        return float(convert_quantity(
            float(lot.get("quantity") or 0),
            str(lot.get("unit") or "g"),
            "g",
            lot.get("thousand_seed_weight_g"),
        ))
    except ValueError:
        return None


def _allocation_for_crop(payload: dict, crop: str, required_g: float) -> tuple[list[dict], float, list[int]]:
    """Allocate grams across matching lots without mutating inventory.

    Oldest/earliest-expiring lots are consumed first. Lots that cannot be
    converted to grams are reported and skipped rather than guessed.
    """
    lots = _matching_lots(payload, crop)
    lots.sort(key=lambda lot: (
        lot.get("expiry_date") or "9999-12-31",
        lot.get("purchase_date") or "9999-12-31",
        int(lot.get("id") or 0),
    ))
    remaining = float(required_g)
    allocation: list[dict] = []
    unconvertible: list[int] = []
    available_total = 0.0
    for lot in lots:
        available_g = _available_grams(lot)
        if available_g is None:
            unconvertible.append(int(lot["id"]))
            continue
        available_total += available_g
        if remaining <= 1e-9:
            continue
        take_g = min(remaining, available_g)
        if take_g > 0:
            allocation.append({
                "lot_id": int(lot["id"]),
                "crop": crop,
                "variety": lot.get("variety"),
                "lot_unit": lot["unit"],
                "take_g": round(take_g, 4),
            })
            remaining -= take_g
    return allocation, round(available_total, 4), unconvertible


def plan_mix_against_inventory(
    recipe_id: str,
    width_m: float,
    length_m: float,
    seed_rates_g_m2: dict[str, float],
    reserve_pct: float = 5.0,
    payload: dict | None = None,
) -> dict:
    """Preview a mix against the user's real Seed Inventory lots."""
    payload = payload if payload is not None else load_inventory()
    plan = calculate_mix_seed_requirements(
        recipe_id, width_m, length_m, seed_rates_g_m2, reserve_pct
    )
    shortages = []
    components = []
    for component in plan["components"]:
        required = component.get("required_seed_g")
        if required is None:
            components.append({
                **component,
                "available_seed_g": None,
                "shortage_g": None,
                "allocation": [],
                "unconvertible_lot_ids": [],
                "enough_stock": False,
            })
            continue
        allocation, available_g, unconvertible = _allocation_for_crop(
            payload, component["crop"], float(required)
        )
        shortage = round(max(0.0, float(required) - available_g), 4)
        enough = shortage <= 1e-9
        if not enough:
            shortages.append({"crop": component["crop"], "shortage_g": shortage})
        components.append({
            **component,
            "available_seed_g": round(available_g, 4),
            "shortage_g": shortage,
            "allocation": allocation,
            "unconvertible_lot_ids": unconvertible,
            "enough_stock": enough,
        })
    return {
        **plan,
        "components": components,
        "shortages": shortages,
        "inventory_ready": plan["ready"] and not shortages,
    }


def consume_mix_from_inventory(
    recipe_id: str,
    width_m: float,
    length_m: float,
    seed_rates_g_m2: dict[str, float],
    reserve_pct: float = 5.0,
    reference: str | None = None,
) -> dict:
    """Validate and atomically deduct all mix components from Seed Inventory.

    Inventory is loaded once, all lots are validated first, all deductions are
    applied in memory, then one save replaces the inventory file. A transaction
    row is added for every consumed lot so history remains auditable.
    """
    payload = load_inventory()
    plan = plan_mix_against_inventory(
        recipe_id, width_m, length_m, seed_rates_g_m2, reserve_pct, payload
    )
    if not plan["inventory_ready"]:
        raise ValueError("Mešanice ni mogoče knjižiti: manjka setvena norma ali zadostna zaloga semena.")

    lots_by_id = {int(lot["id"]): lot for lot in payload.get("lots", [])}
    # Validate conversions and balances again before mutating anything.
    deductions: list[tuple[dict, float, float]] = []
    for component in plan["components"]:
        for row in component["allocation"]:
            lot = lots_by_id.get(int(row["lot_id"]))
            if lot is None:
                raise ValueError("Semenska serija se je med potrditvijo spremenila. Ponovi pregled zaloge.")
            take_g = float(row["take_g"])
            take_lot_unit = convert_quantity(
                take_g, "g", lot["unit"], lot.get("thousand_seed_weight_g")
            )
            if float(lot["quantity"]) + 1e-9 < take_lot_unit:
                raise ValueError("Zaloga semena se je med potrditvijo zmanjšala. Ponovi pregled zaloge.")
            deductions.append((lot, take_g, take_lot_unit))

    now = datetime.utcnow().isoformat() + "Z"
    txs = payload.setdefault("transactions", [])
    next_tx = max([int(tx.get("id") or 0) for tx in txs] or [0]) + 1
    for lot, take_g, take_lot_unit in deductions:
        lot["quantity"] = round(max(0.0, float(lot["quantity"]) - take_lot_unit), 4)
        lot["updated_at"] = now
        txs.append({
            "id": next_tx,
            "lot_id": int(lot["id"]),
            "quantity": round(-take_g, 4),
            "unit": "g",
            "quantity_in_lot_unit": round(-take_lot_unit, 4),
            "reason": "baby_leaf_mix_sowing",
            "reference": reference or recipe_id,
            "created_at": now,
        })
        next_tx += 1

    save_inventory(payload)
    return {
        **plan,
        "committed": True,
        "reference": reference or recipe_id,
        "transactions_created": len(deductions),
    }
