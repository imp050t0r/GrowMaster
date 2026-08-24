"""Planting-window guidance for a temperate Slovenian market garden.

Month lists are a practical baseline for central Slovenia.  Exact dates still
depend on altitude, the current season, soil temperature, frost, and protection.
"""

CALENDAR_FIELDS = (
    "planting_method",
    "outdoor_months",
    "protected_months",
    "heat_tolerance",
    "cold_tolerance",
    "planting_calendar_note",
    "succession_interval_days",
    "calendar_source_url",
)

SUCCESSION_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/methods-tools-supplies/"
    "succession-planting/succession-planting-interval-chart-vegetables.html"
)
PLANTING_PROGRAMS_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/methods-tools-supplies/"
    "succession-planting/planting-programs.html"
)
SPINACH_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/vegetables/spinach/"
    "spinach-varieties-planting-program-comparison-chart.html"
)
BROCCOLI_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/vegetables/broccoli/broc.html"
)
LETTUCE_SOURCE = (
    "https://www.johnnyseeds.com/growers-library/vegetables/lettuce/"
    "lettuceprogram.html"
)


def calendar(
    method: str,
    outdoor: str,
    protected: str,
    heat: str,
    cold: str,
    note: str,
    succession: int | None = None,
    source: str | None = None,
) -> dict:
    return {
        "planting_method": method,
        "outdoor_months": outdoor,
        "protected_months": protected,
        "heat_tolerance": heat,
        "cold_tolerance": cold,
        "planting_calendar_note": note,
        "succession_interval_days": succession,
        "calendar_source_url": source,
    }


# Variety-specific windows combine Johnny's seasonal traits and planting
# programs with a conservative central-Slovenia frost calendar.  Disjoint month
# lists intentionally preserve separate spring and autumn planting windows.
JOHNNYS_VARIETY_CALENDARS = {
    ("Rukola", "Astro"): calendar(
        "direct", "3,4,5,6,7,8,9,10", "2,3,4,5,6,7,8,9,10,11",
        "visoka", "visoka",
        "Najboljša je spomladi in jeseni; zaradi toplotne tolerance jo lahko ob stalni vlagi sejemo tudi poleti.",
        14,
    ),
    ("Solata", "Muir"): calendar(
        "transplant", "4,5,6,7,8", "3,4,5,6,7,8,9",
        "visoka", "srednja",
        "Poletna batavia; presajaj od pomladi do poznega poletja, v vročini pa hladi setvene platoje.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Breen"): calendar(
        "transplant", "3,4,5,6,8,9", "2,3,4,5,6,7,8,9,10",
        "visoka", "srednja",
        "Najzanesljivejša je spomladi in jeseni; poleti jo presajaj zvečer in po potrebi senči.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Truchas"): calendar(
        "transplant", "3,4,5,6,8,9", "2,3,4,5,6,7,8,9,10",
        "visoka", "srednja",
        "Mini rimska solata za pomlad in jesen; toplotna toleranca omogoča tudi zmerne poletne termine.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Green Saladbowl"): calendar(
        "transplant", "3,4,5,8,9", "2,3,4,5,8,9,10",
        "srednja", "srednja",
        "Klasičen zelen hrastov list za hladnejšo pomlad in jesen; za baby leaf ga sej neposredno v kratkih turnusih.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Red Saladbowl"): calendar(
        "transplant", "3,4,5,8,9", "2,3,4,5,8,9,10",
        "srednja", "srednja",
        "Najlepšo rdečo barvo razvije v hladnejših terminih; za baby leaf ga sej neposredno.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Panisse"): calendar(
        "transplant", "3,4,5,6,7,8,9", "2,3,4,5,6,7,8,9,10",
        "visoka", "srednja",
        "Toplotno tolerantnejši hrastov list za podaljšano poletno pridelavo; setvene platoje v vročini hladi in senči.",
        14, LETTUCE_SOURCE,
    ),
    ("Solata", "Oscarde"): calendar(
        "transplant", "3,4,5,8,9", "1,2,3,4,5,8,9,10,11,12",
        "srednja", "srednja",
        "Hitra rdeča sorta za pomlad in jesen ter zimski rastlinjak; poleti jo sej v hladnem substratu in po potrebi senči.",
        14, LETTUCE_SOURCE,
    ),
    ("Špinača", "Tragopan"): calendar(
        "direct", "2,3,4,8,9,10", "1,2,3,4,9,10,11,12",
        "nizka", "visoka",
        "Hitro rastoča hladnosezonska sorta; ne sej je v glavni poletni vročini.",
        7, SPINACH_SOURCE,
    ),
    ("Špinača", "Space"): calendar(
        "direct", "2,3,4,5,8,9,10", "1,2,3,4,5,9,10,11,12",
        "srednja", "visoka",
        "Široko uporabna od pozne zime do pomladi in ponovno od poznega poletja.",
        7, SPINACH_SOURCE,
    ),
    ("Špinača", "Flamingo Improved"): calendar(
        "direct", "2,3,4,8,9,10", "1,2,3,4,9,10,11,12",
        "nizka", "visoka",
        "Najprimernejša za hladne, hitro rastoče pomladne in jesenske turnuse.",
        7, SPINACH_SOURCE,
    ),
    ("Korenje", "Mokum"): calendar(
        "direct", "2,3,4,5,6", "1,2,3,4,10,11,12",
        "srednja", "srednja",
        "Zgodnje korenje; sej od konca zime do zgodnjega poletja, za najzgodnejše šope pod zaščito.",
        21, SUCCESSION_SOURCE,
    ),
    ("Korenje", "Napoli"): calendar(
        "direct", "2,3,4,8,9", "1,2,3,9,10,11",
        "nizka", "visoka",
        "Posebej primerno za pozno poletno oziroma jesensko setev in prezimovanje pod zaščito.",
        21, SUCCESSION_SOURCE,
    ),
    ("Korenje", "Bolero"): calendar(
        "direct", "4,5,6,7", "3,4,5,6",
        "srednja", "srednja",
        "Glavna skladiščna sorta; za jesensko spravilo jo sej predvsem junija in do sredine julija.",
        21, SUCCESSION_SOURCE,
    ),
    ("Rdeča pesa", "Boro"): calendar(
        "direct", "3,4,5,6,7,8", "2,3,4,5,6,7,8,9",
        "srednja", "srednja",
        "Za sprotno prodajo sej na 14 dni; julijske setve so primerne za jesensko spravilo in skladiščenje.",
        14, SUCCESSION_SOURCE,
    ),
    ("Rdeča pesa", "Zeppo"): calendar(
        "direct", "3,4,5,6,7,8", "2,3,4,5,6,7,8,9",
        "srednja", "srednja",
        "Primerna za zaporedne setve, baby korene in šope od pomladi do jeseni.",
        14, SUCCESSION_SOURCE,
    ),
    ("Redkvica", "Rover"): calendar(
        "direct", "2,3,4,5,6,7,8,9,10", "1,2,3,4,5,6,7,8,9,10,11,12",
        "visoka", "visoka",
        "Zaradi toplotne tolerance pokriva dolgo sezono; poleti potrebuje stalno vlago in hitro spravilo.",
        7, SUCCESSION_SOURCE,
    ),
    ("Redkvica", "Sora"): calendar(
        "direct", "3,4,5,8,9,10", "2,3,4,5,9,10,11",
        "srednja", "visoka",
        "Najboljša v hladnejših pomladnih in jesenskih terminih.",
        7, SUCCESSION_SOURCE,
    ),
    ("Zelje", "Farao"): calendar(
        "transplant", "3,4,5,6,7", "2,3,4,5,6,7,8",
        "visoka", "visoka",
        "Zgodnje zelje za pomladne saditve, vendar dobro prenaša tudi tople poletne in hladne jesenske termine.",
        21,
    ),
    ("Zelje", "Tiara"): calendar(
        "transplant", "3,4,5,7", "2,3,4,5,6",
        "srednja", "srednja",
        "Zelo zgodnja sorta; glavne saditve načrtuj spomladi, dodatni turnus pa v začetku poletja.",
        21,
    ),
    ("Brokoli", "Belstar"): calendar(
        "transplant", "3,4,5,6,7", "2,3,4,5,6,7,8",
        "srednja", "visoka",
        "Primeren za pomladne in poletne saditve ter jesensko spravilo.",
        21, BROCCOLI_SOURCE,
    ),
    ("Brokoli", "Imperial"): calendar(
        "transplant", "5,6,7", "4,5,6,7,8",
        "visoka", "srednja",
        "Toplotno tolerantna sorta za pozno pomladne in poletne saditve.",
        21, BROCCOLI_SOURCE,
    ),
    ("Brokoli", "Kariba"): calendar(
        "transplant", "6,7,8", "5,6,7,8,9",
        "nizka", "visoka",
        "Hladno odporna sorta za poletno saditev in jesensko oziroma zgodnje zimsko spravilo.",
        21, BROCCOLI_SOURCE,
    ),
    ("Cvetača", "Snow Crown"): calendar(
        "transplant", "3,4,5,7,8", "2,3,4,5,7,8,9",
        "srednja", "visoka",
        "Zgodnja in prilagodljiva; najboljša za pomladni ali jesenski pridelek, ne za vrhunec poletja.",
        21, PLANTING_PROGRAMS_SOURCE,
    ),
    ("Koleraba", "Kossak"): calendar(
        "transplant", "5,6,7", "4,5,6,7",
        "srednja", "visoka",
        "Skladiščna koleraba; sadi pozno spomladi in poleti za jesensko spravilo.",
        21, SUCCESSION_SOURCE,
    ),
    ("Japonska repa", "Hakurei"): calendar(
        "direct", "3,4,5,8,9", "2,3,4,5,6,8,9,10,11",
        "nizka", "visoka",
        "Hladnosezonska solatna repa; izogni se vročemu in suhemu delu poletja.",
        14, SUCCESSION_SOURCE,
    ),
    ("Koromač", "Preludio"): calendar(
        "transplant", "6,7,8", "5,6,7,8",
        "nizka", "srednja",
        "Najbolj zanesljiv ob krajšanju dneva: sadi poleti za pozno poletno in jesensko spravilo.",
        21,
    ),
    ("Por", "King Richard"): calendar(
        "transplant", "3,4,5", "2,3,4,5",
        "srednja", "srednja",
        "Sej v platoje januarja–marca in presajaj zgodaj za poletni oziroma zgodnje jesenski pridelek.",
        None,
    ),
    ("Por", "Bandit"): calendar(
        "transplant", "5,6,7", "4,5,6,7",
        "srednja", "visoka",
        "Pozni zimski por; sej zgodaj spomladi in presajaj pozno spomladi ali poleti.",
        None,
    ),
    ("Fižol", "Provider"): calendar(
        "direct", "5,6,7", "4,5,6,7,8",
        "visoka", "nizka",
        "Sej šele v ogreta tla po nevarnosti slane; za neprekinjen pridelek ponovi setev na 14 dni.",
        14, SUCCESSION_SOURCE,
    ),
    ("Fižol", "Fortex"): calendar(
        "direct", "5,6", "4,5,6,7",
        "visoka", "nizka",
        "Visoki fižol sej po slani v topla tla; poznejše setve potrebujejo dovolj dolgo jesen.",
        21,
    ),
    ("Grah", "Sugar Ann"): calendar(
        "direct", "2,3,4,8", "1,2,3,4,8,9",
        "nizka", "visoka",
        "Zelo zgodnji grah za prve spomladanske setve; možen je tudi zgodnji jesenski turnus.",
        10, SUCCESSION_SOURCE,
    ),
    ("Grah", "Sugar Snap"): calendar(
        "direct", "2,3,4,8", "1,2,3,4,8,9",
        "nizka", "visoka",
        "Sej zgodaj spomladi ali približno osem tednov pred prvo jesensko slano; potrebuje oporo.",
        10, SUCCESSION_SOURCE,
    ),
    ("Paradižnik", "Defiant PhR"): calendar(
        "transplant", "5,6", "4,5,6",
        "visoka", "nizka",
        "Na prosto presajaj po zadnji slani; za zgodnejši pridelek uporabi neogrevan tunel.",
        28,
    ),
    ("Paradižnik", "Mountain Magic"): calendar(
        "transplant", "5,6", "4,5,6",
        "visoka", "nizka",
        "Na prosto presajaj po zadnji slani in takoj zagotovi oporo; v tunel lahko približno mesec prej.",
        28,
    ),
    ("Paprika", "Carmen"): calendar(
        "transplant", "5,6", "4,5,6",
        "visoka", "nizka",
        "Presajaj v dobro ogreta tla; za polno rdečo zrelost je tunel varnejši v hladnejših območjih.",
        None,
    ),
    ("Paprika", "Escamillo"): calendar(
        "transplant", "5,6", "4,5,6",
        "visoka", "nizka",
        "Presajaj v dobro ogreta tla; za polno rumeno zrelost potrebuje dolgo toplo sezono.",
        None,
    ),
    ("Kumara", "Diva"): calendar(
        "direct", "5,6,7", "4,5,6,7",
        "visoka", "nizka",
        "Sej ali presajaj šele v topla tla; za neprekinjeno spravilo ponovi setev po treh tednih.",
        21, SUCCESSION_SOURCE,
    ),
    ("Kumara", "Socrates"): calendar(
        "transplant", "5,6", "4,5,6,7",
        "visoka", "nizka",
        "Prednostno za tunel; vzgoji 3–4 tedne stare sadike in jih presadi v ogreta tla.",
        21,
    ),
    ("Bučka", "Dunja"): calendar(
        "direct", "5,6,7", "4,5,6,7",
        "visoka", "nizka",
        "Sej po nevarnosti slane; drugi turnus po približno 30 dneh podaljša poletno spravilo.",
        30, SUCCESSION_SOURCE,
    ),
    ("Zelena", "Tango"): calendar(
        "transplant", "4,5,6", "3,4,5,6",
        "srednja", "srednja",
        "Vzgoja sadik traja dolgo; presajaj spomladi in nato ves čas zagotavljaj enakomerno vlago.",
        None,
    ),
}


def default_calendar_for_crop(crop_name: str, category: str = "") -> dict:
    """Return a conservative crop-level fallback for old or user-added varieties."""
    name = crop_name.casefold()
    category_name = category.casefold()

    if category_name == "baby leaf" or "baby leaf" in name or name in {
        "mladi listi rdeče pese", "divja rukola",
    }:
        return calendar(
            "direct", "2,3,4,5,8,9,10", "1,2,3,4,5,6,7,8,9,10,11,12",
            "srednja", "visoka",
            "Baby-leaf posevek sej v kratkih zaporednih turnusih; poleti poskrbi za hlajenje in vlago.",
            7, SUCCESSION_SOURCE,
        )

    transplant_warm = {
        "paradižnik", "paprika", "feferon", "jajčevec", "indijski jajčevec",
        "indijski čili", "nepalski zeleni čili", "bamija", "zelena",
    }
    direct_warm = {
        "kumara", "bučka", "buča", "fižol", "edamame", "lauki", "karela",
        "rebrasta bučka", "gobasta bučka", "tinda", "voščena buča", "guar",
        "shiso", "malabarska špinača", "listni amarant",
    }
    cool_transplant = {
        "solata", "endivija", "zelje", "cvetača", "brokoli", "koleraba",
        "koromač", "por", "radič", "pak choi", "pekinško zelje",
    }
    cool_direct = {
        "rukola", "špinača", "motovilec", "grah", "bob", "redkvica",
        "rdeča pesa", "repa", "japonska repa", "korenje", "daikon",
        "mizuna", "mibuna", "tatsoi", "komatsuna", "choi sum", "kailan",
        "azijska gorčica", "shungiku", "methi", "koriander", "palak",
        "salatni trpotec",
    }

    if name in transplant_warm:
        return calendar(
            "transplant", "5,6", "4,5,6,7", "visoka", "nizka",
            "Toploljubno kulturo presajaj po zadnji slani in v dobro ogreta tla.",
            None, SUCCESSION_SOURCE,
        )
    if name in direct_warm:
        return calendar(
            "direct", "5,6,7", "4,5,6,7,8", "visoka", "nizka",
            "Sej po zadnji slani, ko so tla dovolj ogreta.",
            21, SUCCESSION_SOURCE,
        )
    if name in cool_transplant:
        return calendar(
            "transplant", "3,4,5,7,8,9", "2,3,4,5,6,7,8,9,10",
            "srednja", "visoka",
            "Najzanesljivejši so pomladni in pozno poletni oziroma jesenski termini.",
            14, PLANTING_PROGRAMS_SOURCE,
        )
    if name in cool_direct or category_name == "azijska":
        return calendar(
            "direct", "2,3,4,5,8,9,10", "1,2,3,4,5,8,9,10,11,12",
            "nizka", "visoka",
            "Hladnosezonska kultura za pomlad in jesen; poletne setve so bolj tvegane.",
            14, SUCCESSION_SOURCE,
        )
    if category_name == "indijska":
        return calendar(
            "direct", "5,6,7", "4,5,6,7,8", "visoka", "nizka",
            "Toploljubno kulturo sej po zadnji slani in v dobro ogreta tla.",
            21, SUCCESSION_SOURCE,
        )
    return calendar(
        "direct", "3,4,5,6,7,8,9", "2,3,4,5,6,7,8,9,10",
        "srednja", "srednja",
        "To je splošno priporočilo po vrsti zelenjave; termin prilagodi lokalni slani in temperaturi tal.",
        None, None,
    )
