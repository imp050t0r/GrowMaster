from types import SimpleNamespace

from app.adaptive_recommendations import apply_yield_evidence, yield_evidence


def cycle(bed, crop, kg):
    return SimpleNamespace(
        bed_id=bed, crop_id=crop,
        harvests=[SimpleNamespace(quantity_kg=kg)],
    )


def test_repeated_results_shift_ranking_but_single_result_does_not():
    evidence = yield_evidence(
        [cycle(1, 7, 20), cycle(1, 7, 22), cycle(2, 7, 4), cycle(2, 7, 5)],
        {1: 10, 2: 10},
    )
    assert evidence[1, 7]["score_adjustment"] > 0
    assert evidence[2, 7]["score_adjustment"] < 0
    assert evidence[1, 7]["harvest_count"] == 2

    single = yield_evidence([cycle(1, 7, 100), cycle(2, 7, 1)], {1: 10, 2: 10})
    assert single[1, 7]["score_adjustment"] == 0
    assert single[2, 7]["score_adjustment"] == 0


def test_learning_preserves_rotation_warnings():
    result = {"score": 35, "rating": "caution", "rating_label": "Previdno",
              "reasons": [], "warnings": ["Ista družina v zadnjem ciklu."]}
    apply_yield_evidence(result, {"harvest_count": 3, "yield_kg_m2": 5,
                                  "farm_yield_kg_m2": 2, "score_adjustment": 12})
    assert result["score"] == 47
    assert result["rating"] == "caution"
    assert "Ista družina v zadnjem ciklu." in result["warnings"]
