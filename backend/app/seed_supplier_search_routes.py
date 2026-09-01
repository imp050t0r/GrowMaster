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
SOURCE_BY_KEY = {source.key: source for source in SOURCES}

# Verified product pages are a deterministic first tier. They are intentionally
# small and curated. Generic web search remains the second tier and can discover
# additional sellers without pretending that an unverified search result is a
# confirmed product page.
VERIFIED_PRODUCT_LINKS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    ("koriander", "calypso"): (
        (
            "voltz",
            "https://de.de-shop.voltz-maraichage.com/konventionelles-saatgut/koriander-calypso",
        ),
        ("tozer", "https://www.tozerseeds.com/product/coriander-calypso/"),
    ),
    ("koriander", "confetti"): (
        ("tozer", "https://www.tozerseeds.com/product/coriander-confetti/"),
    ),
    ("koriander", "cruiser"): (
        (
            "johnnys",
            "https://www.johnnyseeds.com/herbs/cilantro-coriander/cruiser-organic-cilantro-coriander-seed-3755G.32.html",
        ),
    ),
    ("koriander", "leisure"): (
        (
            "johnnys",
            "https://www.johnnyseeds.com/herbs/cilantro-coriander/leisure-cilantro-coriander-seed-3409.11.html",
        ),
    ),
    ("koriander", "santo"): (
        (
            "johnnys",
            "https://prod-na02.johnnyseeds.com/herbs/cilantro-coriander/santo-cilantro-coriander-seed-919.html",
        ),
    ),
}

_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60 * 30
PRICE_RE = re.compile(
    r"(?:(?:€|EUR)\s*([0-9]+(?:[.,][0-9]{1,2})?)|([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:€|EUR))",
    re.I,
)
ANCHOR_RE = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

# Plant DB uses Slovenian crop names. Supplier pages usually use English, German,
# French or Dutch names, so a literal quoted Slovenian crop name is too strict.
# These aliases are only search hints; they never replace GrowMaster master data.
CROP_SEARCH_ALIASES = {
    "solata": "lettuce",
    "rukola": "arugula rocket rucola",
    "koriander": "coriander cilantro koriander dhania coriandrum sativum",
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
    "karela": "grenka bučka grenka bucka grenka melona bitter melon bitter gourd karavella momordica charantia",
    "grenka bučka": "karela bitter melon bitter gourd karavella momordica charantia",
    "grenka bucka": "karela bitter melon bitter gourd karavella momordica charantia",
    "grenka melona": "karela bitter melon bitter gourd karavella momordica charantia",
    "lauki": "bottle gourd",
    "rebrasta bučka": "ridge gourd turai tori luffa acutangula",
    "gobasta bučka": "sponge gourd smooth luffa gilki luffa cylindrica",
    "tinda": "round melon apple gourd indian round gourd praecitrullus fistulosus",
    "voščena buča": "wax gourd ash gourd winter melon petha benincasa hispida",
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


def _supplier_for_url(url: str) -> SupplierSource | None:
    return next((source for source in SOURCES if _domain_matches(url, source.domain)), None)


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
                "verified": False,
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


def _fetch_page(url: str, timeout: int = 7) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrowMaster/1.24 seed-search",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - controlled HTTPS sources/search hosts
        return response.read(900_000).decode("utf-8", errors="replace")


def _search_source(source: SupplierSource, crop: str, variety: str | None) -> tuple[list[dict], list[dict], int]:
    failures: list[dict] = []
    attempts = 0
    for query in _query_variants(source, crop, variety):
        for engine, url in _search_urls(query):
            attempts += 1
            try:
                page = _fetch_page(url)
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
        "verified": False,
    }


def _find_crop(db: Session, crop_name: str):
    crops = db.scalars(select(Crop).options(selectinload(Crop.varieties))).all()
    return next((item for item in crops if item.name.casefold() == crop_name.casefold()), None)


def _verified_candidates(db: Session, crop: str, variety: str | None, eu_only: bool) -> list[tuple[SupplierSource, str, str]]:
    if not variety:
        return []
    candidates: list[tuple[SupplierSource, str, str]] = []
    seen: set[str] = set()

    crop_record = _find_crop(db, crop)
    if crop_record is not None:
        variety_record = next(
            (item for item in crop_record.varieties if item.name.casefold() == variety.casefold()),
            None,
        )
        source_url = getattr(variety_record, "source_url", None) if variety_record else None
        source = _supplier_for_url(source_url) if source_url else None
        if source is not None and (not eu_only or source.eu):
            candidates.append((source, source_url, "plant-db-source"))
            seen.add(source_url)

    for supplier_key, url in VERIFIED_PRODUCT_LINKS.get((crop.casefold(), variety.casefold()), ()):
        source = SOURCE_BY_KEY[supplier_key]
        if (eu_only and not source.eu) or url in seen:
            continue
        candidates.append((source, url, "verified-product-link"))
        seen.add(url)
    return candidates


def _verified_offer(source: SupplierSource, url: str, crop: str, variety: str, origin: str) -> tuple[dict, dict | None]:
    page = ""
    error = None
    try:
        page = _fetch_page(url, timeout=6)
    except Exception as exc:
        error = {
            "supplier": source.name,
            "engine": origin,
            "error": type(exc).__name__,
        }
    title_match = TITLE_RE.search(page) if page else None
    title = _clean(title_match.group(1)) if title_match else f"{variety} · {source.name}"
    price = _price(_clean(page)) if page else None
    offer = {
        "supplier_key": source.key,
        "supplier": source.name,
        "country": source.country,
        "eu": source.eu,
        "title": title,
        "snippet": "Preverjena neposredna stran sorte iz GrowMaster baze oziroma kuriranega kataloga izdelkov.",
        "url": url,
        "price_eur": price,
        "in_stock": None,
        "package": None,
        "seed_form": None,
        "organic": None,
        "score": 1000 + _score(title, "", crop, variety, source.eu, price),
        "source": origin,
        "is_fallback": False,
        "verified": True,
    }
    return offer, error


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
    db: Session = Depends(get_db),
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

    if variety:
        for source, url, origin in _verified_candidates(db, crop, variety, eu_only):
            offer, error = _verified_offer(source, url, crop, variety, origin)
            offers.append(offer)
            if error:
                errors.append(error)

    def run(source: SupplierSource):
        results, failures, attempts = _search_source(source, crop, variety)
        return source, results, failures, attempts

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

    # Keep one card per real URL. A verified direct link wins over a generic web
    # result to the same product page.
    unique: dict[str, dict] = {}
    for offer in offers:
        key = offer["url"]
        current = unique.get(key)
        if current is None or (offer.get("verified") and not current.get("verified")):
            unique[key] = offer
    offers = list(unique.values())

    if in_stock_only:
        offers = [offer for offer in offers if offer["in_stock"] is not False]

    direct_count = sum(1 for offer in offers if not offer["is_fallback"])
    verified_count = sum(1 for offer in offers if offer.get("verified"))
    fallback_count = sum(1 for offer in offers if offer["is_fallback"])
    offers.sort(
        key=lambda item: (
            item["is_fallback"],
            not item.get("verified", False),
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
        "verified_count": verified_count,
        "fallback_count": fallback_count,
        "supplier_count": len(sources),
        "errors": errors,
        "source_status": source_status,
        "cached": False,
        "live": direct_count > 0,
        "degraded": direct_count == 0,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": (
            "GrowMaster najprej uporabi preverjene neposredne strani sorte iz Plant DB in kuriranega kataloga. "
            "Nato išče dodatne ponudbe prek več spletnih iskalnikov. Če izdelka ne more zanesljivo razpoznati, "
            "prikaže rezervno ciljno iskalno povezavo. Cene in zaloga so prikazane samo, kadar jih stran zanesljivo vsebuje."
        ),
    }
    _CACHE[cache_key] = (time.time(), payload)
    return payload
