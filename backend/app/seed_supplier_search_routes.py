from __future__ import annotations

import base64
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Crop

router = APIRouter()


@dataclass(frozen=True)
class SupplierSource:
    key: str
    name: str
    domain: str
    country: str
    eu: bool


SOURCES = (
    SupplierSource("reinsaat", "ReinSaat", "reinsaat.at", "AT", True),
    SupplierSource("bingenheimer", "Bingenheimer Saatgut", "bingenheimersaatgut.de", "DE", True),
    SupplierSource("hiseed", "HiSeed", "hiseed.it", "IT", True),
    SupplierSource("voltz", "Graines Voltz", "voltz-maraichage.com", "FR", True),
    SupplierSource("sativa", "Sativa Rheinau", "sativa.bio", "CH", False),
    SupplierSource("kokopelli", "Kokopelli", "kokopelli-semences.fr", "FR", True),
    SupplierSource("tozer", "Tozer Seeds", "tozerseeds.com", "UK", False),
    SupplierSource("johnnys", "Johnny's Selected Seeds", "johnnyseeds.com", "US", False),
    SupplierSource("bejo", "Bejo", "bejo.com", "NL", True),
    SupplierSource("rijkzwaan", "Rijk Zwaan", "rijkzwaan.com", "NL", True),
    SupplierSource("enzazaden", "Enza Zaden", "enzazaden.com", "NL", True),
)

_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60 * 30
PRICE_RE = re.compile(
    r"(?:(?:€|EUR)\s*([0-9]+(?:[.,][0-9]{1,2})?)|([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:€|EUR))",
    re.I,
)
ANCHOR_RE = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

# Plant DB uses Slovenian crop names. Supplier pages usually use English, German,
# French or Dutch names, so a literal quoted Slovenian crop name is too strict.
# These aliases are only search hints; they never replace GrowMaster master data.
CROP_SEARCH_ALIASES = {
    "solata": "lettuce",
    "rukola": "arugula rocket rucola",
    "koriander": "coriander cilantro koriander",
    "paprika": "pepper capsicum paprika",
    "čili": "chili chilli pepper",
    "paradižnik": "tomato",
    "korenje": "carrot",
    "čebula": "onion",
    "špinača": "spinach",
    "redkev": "radish",
    "redkvica": "radish",
    "pesa": "beet beetroot",
    "blitva": "chard",
    "mangold": "chard",
    "ohrovt": "kale",
    "zelje": "cabbage",
    "brokoli": "broccoli",
    "cvetača": "cauliflower",
    "kumara": "cucumber",
    "bučka": "zucchini courgette",
    "buča": "squash pumpkin",
    "jajčevec": "eggplant aubergine",
    "grah": "pea",
    "fižol": "bean",
    "koromač": "fennel",
    "koper": "dill",
    "peteršilj": "parsley",
    "bazilika": "basil",
    "motovilec": "corn salad lambs lettuce",
    "endivija": "endive",
    "radič": "chicory radicchio",
    "por": "leek",
    "repa": "turnip",
    "koleraba": "kohlrabi",
    "gorčica": "mustard",
    "kreša": "cress",
    "methi": "fenugreek",
    "dhania": "coriander cilantro",
    "bhindi": "okra",
    "okra": "okra",
    "karela": "bitter melon bitter gourd",
    "lauki": "bottle gourd",
}


def _clean(value: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", value)).replace("\n", " ").split())


def _decode_bing_target(parsed) -> str | None:
    if "bing.com" not in parsed.netloc.casefold() or "/ck/a" not in parsed.path:
        return None
    encoded = parse_qs(parsed.query).get("u", [None])[0]
    if not encoded or not encoded.startswith("a1"):
        return None
    payload = encoded[2:]
    payload += "=" * (-len(payload) % 4)
    try:
        target = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return target if target.startswith(("http://", "https://")) else None


def _real_url(raw_url: str) -> str:
    raw_url = html.unescape(raw_url)
    parsed = urlparse(raw_url)
    if "duckduckgo.com" in parsed.netloc.casefold():
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    bing_target = _decode_bing_target(parsed)
    if bing_target:
        return bing_target
    return raw_url


def _price(text: str) -> float | None:
    match = PRICE_RE.search(text)
    if not match:
        return None
    raw = (match.group(1) or match.group(2)).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _score(title: str, snippet: str, crop: str, variety: str | None, eu: bool, price: float | None) -> int:
    text = f"{title} {snippet}".casefold()
    score = 15 if crop.casefold() in text else 0
    if variety:
        score += 45 if variety.casefold() in text else -10
    if eu:
        score += 10
    if price is not None:
        score += 5
    if any(word in text for word in ("seed", "seme", "saat", "semence", "samen", "zaden")):
        score += 5
    return score


def _domain_matches(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    domain = domain.casefold().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def _extract_supplier_results(
    page: str,
    source: SupplierSource,
    crop: str,
    variety: str | None,
    engine: str,
) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for match in ANCHOR_RE.finditer(page):
        product_url = _real_url(match.group(1)).split("#", 1)[0]
        if not _domain_matches(product_url, source.domain) or product_url in seen:
            continue
        title = _clean(match.group(2))
        if len(title) < 2:
            continue
        # Search engines change their CSS frequently. Instead of depending on one
        # result class, collect a small amount of neighbouring text as the snippet.
        snippet = _clean(page[match.end() : match.end() + 650])[:360]
        price = _price(f"{title} {snippet}")
        seen.add(product_url)
        results.append(
            {
                "supplier_key": source.key,
                "supplier": source.name,
                "country": source.country,
                "eu": source.eu,
                "title": title,
                "snippet": snippet,
                "url": product_url,
                "price_eur": price,
                "in_stock": None,
                "package": None,
                "seed_form": None,
                "organic": None,
                "score": _score(title, snippet, crop, variety, source.eu, price),
                "source": f"live-web-search:{engine}",
                "is_fallback": False,
            }
        )
        if len(results) >= 5:
            break
    return results


def _crop_search_terms(crop: str) -> str:
    alias = CROP_SEARCH_ALIASES.get(crop.casefold())
    return alias or crop


def _query_variants(source: SupplierSource, crop: str, variety: str | None) -> list[str]:
    crop_terms = _crop_search_terms(crop)
    variants: list[str] = []
    if variety:
        # Variety names are usually language-independent and are therefore the
        # strongest first query. Do not require the Slovenian crop name to occur
        # on the supplier page.
        variants.append(f'site:{source.domain} "{variety}"')
        variants.append(f'site:{source.domain} "{variety}" {crop_terms}')
    else:
        variants.append(f"site:{source.domain} {crop_terms}")
    return variants


def _search_urls(query: str) -> tuple[tuple[str, str], ...]:
    encoded = quote_plus(query)
    return (
        ("duckduckgo-html", f"https://html.duckduckgo.com/html/?q={encoded}"),
        ("bing", f"https://www.bing.com/search?q={encoded}"),
        ("duckduckgo-lite", f"https://lite.duckduckgo.com/lite/?q={encoded}"),
    )


def _fetch_search_page(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrowMaster/1.24 seed-search",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    with urlopen(request, timeout=7) as response:  # nosec B310 - fixed HTTPS search hosts
        return response.read(900_000).decode("utf-8", errors="replace")


def _search_source(source: SupplierSource, crop: str, variety: str | None) -> tuple[list[dict], list[dict], int]:
    failures: list[dict] = []
    attempts = 0
    for query in _query_variants(source, crop, variety):
        for engine, url in _search_urls(query):
            attempts += 1
            try:
                page = _fetch_search_page(url)
            except Exception as exc:
                failures.append(
                    {
                        "supplier": source.name,
                        "engine": engine,
                        "error": type(exc).__name__,
                    }
                )
                continue
            results = _extract_supplier_results(page, source, crop, variety, engine)
            if results:
                return results, failures, attempts
    return [], failures, attempts


def _fallback_search_link(source: SupplierSource, crop: str, variety: str | None) -> dict:
    query = _query_variants(source, crop, variety)[0]
    return {
        "supplier_key": source.key,
        "supplier": source.name,
        "country": source.country,
        "eu": source.eu,
        "title": f"Išči pri {source.name}",
        "snippet": "Neposreden izdelek ni bil zanesljivo razpoznan. Odpri ciljno spletno iskanje za tega dobavitelja.",
        "url": f"https://www.bing.com/search?q={quote_plus(query)}",
        "price_eur": None,
        "in_stock": None,
        "package": None,
        "seed_form": None,
        "organic": None,
        "score": -100,
        "source": "fallback-search-link",
        "is_fallback": True,
    }


def _catalog_payload(crops) -> dict:
    return {
        "crops": [
            {
                "name": crop.name,
                "varieties": [
                    variety.name
                    for variety in sorted(crop.varieties, key=lambda item: item.name.casefold())
                ],
            }
            for crop in crops
        ]
    }


@router.get("/api/seed-suppliers/catalog")
def seed_supplier_catalog(db: Session = Depends(get_db)) -> dict:
    crops = db.scalars(
        select(Crop).options(selectinload(Crop.varieties)).order_by(Crop.name)
    ).all()
    return _catalog_payload(crops)


@router.get("/api/seed-suppliers")
def seed_suppliers() -> dict:
    return {"suppliers": [source.__dict__ for source in SOURCES]}


@router.get("/api/seed-suppliers/search")
def search_seed_suppliers(
    crop: str = Query(min_length=2, max_length=120),
    variety: str | None = Query(default=None, max_length=120),
    eu_only: bool = Query(default=False),
    in_stock_only: bool = Query(default=False),
    refresh: bool = Query(default=False),
) -> dict:
    crop = crop.strip()
    variety = variety.strip() if variety else None
    cache_key = f"{crop.casefold()}|{(variety or '').casefold()}|{eu_only}|{in_stock_only}"
    cached = _CACHE.get(cache_key)
    if cached and not refresh and time.time() - cached[0] < CACHE_SECONDS:
        return {**cached[1], "cached": True}

    offers: list[dict] = []
    errors: list[dict] = []
    source_status: list[dict] = []
    sources = [source for source in SOURCES if not eu_only or source.eu]

    def run(source: SupplierSource):
        results, failures, attempts = _search_source(source, crop, variety)
        return source, results, failures, attempts

    # Supplier searches are independent. Running them concurrently keeps a
    # degraded search engine from making the whole UI wait source by source.
    workers = min(6, max(1, len(sources)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for source, results, failures, attempts in pool.map(run, sources):
            errors.extend(failures)
            source_status.append(
                {
                    "supplier": source.name,
                    "direct_results": len(results),
                    "attempts": attempts,
                }
            )
            if results:
                offers.extend(results)
            else:
                offers.append(_fallback_search_link(source, crop, variety))

    if in_stock_only:
        # Stock is currently unknown for generic web results. Keep prior
        # behaviour: only exclude a result when stock is explicitly false.
        offers = [offer for offer in offers if offer["in_stock"] is not False]

    direct_count = sum(1 for offer in offers if not offer["is_fallback"])
    fallback_count = sum(1 for offer in offers if offer["is_fallback"])
    offers.sort(
        key=lambda item: (
            item["is_fallback"],
            -item["score"],
            item["supplier"],
            item["title"],
        )
    )
    payload = {
        "crop": crop,
        "variety": variety,
        "offers": offers,
        "offer_count": direct_count,
        "fallback_count": fallback_count,
        "supplier_count": len(sources),
        "errors": errors,
        "source_status": source_status,
        "cached": False,
        "live": direct_count > 0,
        "degraded": direct_count == 0,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": (
            "GrowMaster najprej išče neposredne strani izdelkov prek več spletnih iskalnikov. "
            "Če strani ne more zanesljivo razpoznati, prikaže rezervno ciljno iskalno povezavo. "
            "Cene in zaloga so prikazane samo, kadar jih spletni rezultat zanesljivo vsebuje."
        ),
    }
    _CACHE[cache_key] = (time.time(), payload)
    return payload
