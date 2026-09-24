"""Conservative, local evidence from completed harvests for planting advice."""

from collections import defaultdict
from statistics import median


def yield_evidence(plantings, bed_areas: dict[int, float]) -> dict[tuple[int, int], dict]:
    """Compare each crop on a bed against that crop's recorded farm yields."""
    by_crop = defaultdict(list)
    by_pair = defaultdict(list)
    for planting in plantings:
        area = bed_areas.get(planting.bed_id, 0)
        if area <= 0 or not planting.harvests:
            continue
        yield_per_m2 = sum(h.quantity_kg for h in planting.harvests) / area
        if yield_per_m2 <= 0:
            continue
        by_crop[planting.crop_id].append(yield_per_m2)
        by_pair[(planting.bed_id, planting.crop_id)].append(yield_per_m2)

    evidence = {}
    for (bed_id, crop_id), yields in by_pair.items():
        baseline = median(by_crop[crop_id])
        # One observation is shown, but cannot influence the ranking. Shrink
        # repeated observations toward the crop-wide median and cap the effect.
        count = len(yields)
        relative = (median(yields) / baseline - 1) if baseline else 0
        adjustment = round(max(-12, min(12, relative * 24 * count / (count + 2)))) if count >= 2 else 0
        evidence[(bed_id, crop_id)] = {
            "harvest_count": count,
            "yield_kg_m2": round(median(yields), 2),
            "farm_yield_kg_m2": round(baseline, 2),
            "score_adjustment": adjustment,
        }
    return evidence


def apply_yield_evidence(result: dict, evidence: dict | None) -> dict:
    if not evidence:
        result["yield_evidence"] = None
        return result
    result["yield_evidence"] = evidence
    count = evidence["harvest_count"]
    if count < 2:
        result["reasons"].append("Za kulturo je na tej gredici zabeležena le ena žetev; primerjava še ne vpliva na vrstni red.")
        return result
    adjustment = evidence["score_adjustment"]
    result["score"] = max(0, result["score"] + adjustment)
    result["reasons"].append(
        f"{count} zaključenih pridelav: {evidence['yield_kg_m2']:.2f} kg/m² na gredici "
        f"(mediana kulture na kmetiji {evidence['farm_yield_kg_m2']:.2f} kg/m²)."
    )
    if adjustment < 0:
        result["warnings"].append("Ta kultura je tu doslej dala manj pridelka kot na drugih gredicah.")
    if result["score"] < 70:
        result["rating"], result["rating_label"] = "caution", "Previdno"
    elif result["score"] < 100 or result["warnings"]:
        result["rating"], result["rating_label"] = "acceptable", "Primerno"
    else:
        result["rating"], result["rating_label"] = "recommended", "Zelo primerno"
    return result
