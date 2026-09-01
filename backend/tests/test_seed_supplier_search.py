import base64
from types import SimpleNamespace
from urllib.parse import quote

from app.seed_supplier_search_routes import (
    SupplierSource,
    _catalog_payload,
    _crop_search_terms,
    _extract_supplier_results,
    _fallback_search_link,
    _price,
    _query_variants,
    _real_url,
    _score,
)
from app.south_asian_requested_crops import SOUTH_ASIAN_REQUESTED_CROPS


def test_price_parses_euro_formats():
    assert _price("Cena € 4,50") == 4.5
    assert _price("12.90 EUR") == 12.9
    assert _price("brez cene") is None


def test_duckduckgo_redirect_is_unwrapped():
    url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Freinsaat.at%2Fshop%2Fcalypso"
    assert _real_url(url) == "https://reinsaat.at/shop/calypso"


def test_bing_redirect_is_unwrapped():
    target = "https://www.johnnyseeds.com/herbs/cilantro/calypso-cilantro-seed.html"
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    url = f"https://www.bing.com/ck/a?u={quote('a1' + encoded)}"
    assert _real_url(url) == target


def test_exact_variety_and_eu_rank_higher():
    exact = _score("Calypso coriander seed", "organic seed", "coriander", "Calypso", True, 4.5)
    loose = _score("Coriander seed", "standard seed", "coriander", "Calypso", False, None)
    assert exact > loose


def test_slovenian_crop_gets_multilingual_search_hint():
    assert "coriander" in _crop_search_terms("Koriander")
    assert _crop_search_terms("Unikatna kultura") == "Unikatna kultura"


def test_variety_query_does_not_require_slovenian_crop_name():
    source = SupplierSource("johnnys", "Johnny's", "johnnyseeds.com", "US", False)
    variants = _query_variants(source, "Koriander", "Calypso")
    assert variants[0] == 'site:johnnyseeds.com "Calypso"'
    assert "coriander" in variants[1]


def test_generic_anchor_parser_finds_supplier_result_without_css_class():
    source = SupplierSource("reinsaat", "ReinSaat", "reinsaat.at", "AT", True)
    page = """
    <html><body>
      <a href="https://example.com/nope">Other</a>
      <section><h2><a href="https://www.reinsaat.at/shop/koriander-calypso">Koriander Calypso Saatgut</a></h2>
      <p>Bio Saatgut 4,50 EUR</p></section>
    </body></html>
    """
    results = _extract_supplier_results(page, source, "Koriander", "Calypso", "test")
    assert len(results) == 1
    assert results[0]["url"] == "https://www.reinsaat.at/shop/koriander-calypso"
    assert results[0]["price_eur"] == 4.5
    assert results[0]["is_fallback"] is False


def test_fallback_link_is_not_a_real_offer():
    source = SupplierSource("bejo", "Bejo", "bejo.com", "NL", True)
    fallback = _fallback_search_link(source, "Solata", "Tourbillon")
    assert fallback["is_fallback"] is True
    assert fallback["price_eur"] is None
    assert "site%3Abejo.com" in fallback["url"]


def test_catalog_payload_keeps_crop_variety_dependency_and_sorts_varieties():
    crops = [
        SimpleNamespace(
            name="Koriander",
            varieties=[SimpleNamespace(name="Leisure"), SimpleNamespace(name="Calypso")],
        ),
        SimpleNamespace(
            name="Solata",
            varieties=[SimpleNamespace(name="Tourbillon")],
        ),
    ]

    assert _catalog_payload(crops) == {
        "crops": [
            {"name": "Koriander", "varieties": ["Calypso", "Leisure"]},
            {"name": "Solata", "varieties": ["Tourbillon"]},
        ]
    }


def test_professional_coriander_cultivars_are_in_master_source():
    names = {
        item["name"]
        for item in SOUTH_ASIAN_REQUESTED_CROPS
        if item["crop"] == "Koriander"
    }
    assert {
        "CO-4",
        "Calypso",
        "Cruiser",
        "Leisure",
        "Santo",
        "Confetti",
        "Filtro",
        "Advanced Turbo II",
    }.issubset(names)
