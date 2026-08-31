from app.seed_supplier_search_routes import _price, _real_url, _score


def test_price_parses_euro_formats():
    assert _price("Cena € 4,50") == 4.5
    assert _price("12.90 EUR") == 12.9
    assert _price("brez cene") is None


def test_duckduckgo_redirect_is_unwrapped():
    url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Freinsaat.at%2Fshop%2Fcalypso"
    assert _real_url(url) == "https://reinsaat.at/shop/calypso"


def test_exact_variety_and_eu_rank_higher():
    exact = _score("Calypso coriander seed", "organic seed", "coriander", "Calypso", True, 4.5)
    loose = _score("Coriander seed", "standard seed", "coriander", "Calypso", False, None)
    assert exact > loose
