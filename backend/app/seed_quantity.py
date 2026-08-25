from __future__ import annotations

from math import ceil


def calculate_seed_quantity(
    seed_rate_g_m2: float | None,
    bed_width_m: float,
    bed_length_m: float,
    bed_count: int = 1,
    reserve_percent: float = 5.0,
) -> dict:
    area_per_bed_m2 = round(bed_width_m * bed_length_m, 3)
    total_area_m2 = round(area_per_bed_m2 * bed_count, 3)

    if seed_rate_g_m2 is None:
        return {
            "available": False,
            "seed_rate_g_m2": None,
            "bed_width_m": bed_width_m,
            "bed_length_m": bed_length_m,
            "bed_count": bed_count,
            "area_per_bed_m2": area_per_bed_m2,
            "total_area_m2": total_area_m2,
            "reserve_percent": reserve_percent,
            "seed_g_per_bed": None,
            "seed_g_total": None,
            "seed_g_total_with_reserve": None,
            "seed_kg_total_with_reserve": None,
            "note": "Za kulturo ni določena zanesljiva setvena norma v g/m²; najprej jo določi v sejalniškem master-data profilu.",
        }

    rate = float(seed_rate_g_m2)
    seed_g_per_bed = rate * area_per_bed_m2
    seed_g_total = rate * total_area_m2
    seed_g_total_with_reserve = seed_g_total * (1 + reserve_percent / 100)

    return {
        "available": True,
        "seed_rate_g_m2": round(rate, 3),
        "bed_width_m": bed_width_m,
        "bed_length_m": bed_length_m,
        "bed_count": bed_count,
        "area_per_bed_m2": area_per_bed_m2,
        "total_area_m2": total_area_m2,
        "reserve_percent": reserve_percent,
        "seed_g_per_bed": round(seed_g_per_bed, 2),
        "seed_g_total": round(seed_g_total, 2),
        "seed_g_total_with_reserve": round(seed_g_total_with_reserve, 2),
        "seed_kg_total_with_reserve": round(seed_g_total_with_reserve / 1000, 3),
        "suggested_pack_g": ceil(seed_g_total_with_reserve / 10) * 10,
        "formula": "seed_rate_g_m2 × bed_width_m × bed_length_m × bed_count",
    }
