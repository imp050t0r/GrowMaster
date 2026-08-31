from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query

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
    SupplierSource("sativa", "Sativa Rheinau", "sativa.bio", "CH", False),
    SupplierSource("kokopelli", "Kokopelli", "kokopelli-semences.fr", "FR", True),
    SupplierSource("johnnys", "Johnny's Selected Seeds", "johnnyseeds.com", "US", False),
    SupplierSource("bejo", "Bejo", "bejo.com", "NL", True),
    SupplierSource("rijkzwaan", "Rijk Zwaan", "rijkzwaan.com", "NL", True),
    SupplierSource("enzazaden", "Enza Zaden", "enzazaden.com", "NL", True),
)

_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60 * 30
PRICE_RE = re.compile(r"(?:(?:€|EUR)\s*([0-9]+(?:[.,][0-9]{1,2})?)|([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:€|EUR))", re.I)
RESULT_RE = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SNIPPET_RE = re.compile(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>', re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _clean(value: str) -> str:
    return html.unescape(TAG_RE.sub(" ", value)).replace("\n", " ").strip()


def _real_url(raw_url: str) -> str:
    raw_url = html.unescape(raw_url)
    parsed = urlparse(raw_url)
    if "duckduckgo.com" in parsed.netloc:
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
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
    if any(word in text for word in ("seed", "seme", "saat", "semence", "samen")):
        score += 5
    return score


def _search_source(source: SupplierSource, crop: str, variety: str | None) -> list[dict]:
    terms = f'"{crop}"'
    if variety:
        terms += f' "{variety}"'
    query = quote_plus(f"site:{source.domain} {terms} seed")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 GrowMaster/1.24 seed-search"})
    with urlopen(request, timeout=8) as response:  # nosec B310 - fixed HTTPS host
        page = response.read(750_000).decode("utf-8", errors="replace")

    links = RESULT_RE.findall(page)
    snippets_raw = SNIPPET_RE.findall(page)
    snippets = [_clean(a or b) for a, b in snippets_raw]
    results: list[dict] = []
    for index, (raw_url, raw_title) in enumerate(links[:5]):
        product_url = _real_url(raw_url)
        if source.domain not in urlparse(product_url).netloc.casefold():
            continue
        title = _clean(raw_title)
        snippet = snippets[index] if index < len(snippets) else ""
        price = _price(f"{title} {snippet}")
        results.append({
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
            "source": "live-web-search",
        })
    return results


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
    sources = [source for source in SOURCES if not eu_only or source.eu]
    for source in sources:
        try:
            offers.extend(_search_source(source, crop, variety))
        except Exception as exc:  # one supplier must never break the whole search
            errors.append({"supplier": source.name, "error": type(exc).__name__})

    if in_stock_only:
        offers = [offer for offer in offers if offer["in_stock"] is not False]
    offers.sort(key=lambda item: (-item["score"], item["supplier"], item["title"]))
    payload = {
        "crop": crop,
        "variety": variety,
        "offers": offers,
        "offer_count": len(offers),
        "supplier_count": len(sources),
        "errors": errors,
        "cached": False,
        "live": True,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Cene in zaloga so prikazane samo, kadar jih spletni rezultat zanesljivo vsebuje. GrowMaster ne ugiba manjkajočih podatkov.",
    }
    _CACHE[cache_key] = (time.time(), payload)
    if not offers and len(errors) == len(sources):
        raise HTTPException(status_code=502, detail="Spletno iskanje dobaviteljev trenutno ni dosegljivo.")
    return payload
