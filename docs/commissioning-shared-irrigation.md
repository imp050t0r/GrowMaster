# Pregled konfiguracije in preizkus skupnih ventilov

Stanje: pripravljeno 18. 10. 2026; dejanska namestitev še ni pregledana.
Velja za spremembe v PR #88. To je zapisnik za izvedbo, ne potrdilo delovanja.

## 1. Podatki namestitve

| Podatek | Vrednost za dopolnitev |
| --- | --- |
| GrowMaster različica oziroma commit in lokacija strežnika | še ni potrjeno |
| Home Assistant različica in zasebni naslov domačega Raspberry Pi | še ni potrjeno |
| Smart Irrigation različica | še ni potrjeno |
| Integracija vinteo/hass-opensprinkler različica | še ni potrjeno |
| OpenSprinkler v4 firmware, zasebni naslov in število priključenih izhodov | še ni potrjeno |
| Domače in vrtno omrežje, VPN poti in povratne poti | še ni potrjeno |
| Ecowitt oznaka konzole/prehoda, firmware in način oddaje | uporabnik navaja W3001; preveriti nalepko in zmožnosti |
| WH51 | še niso vgrajeni; brez pripisanih meritev |

Gesla, žetoni in skrivni deli webhook naslovov ne sodijo v ta zapisnik ali Git.
HA žeton se vnese v obstoječe nastavitve povezave GrowMaster.

Preveri tri ločene poti: GrowMaster → HA API; HA → OpenSprinkler prek VPN;
Ecowitt → HA, če konzola podpira oddajanje po protokolu Ecowitt. Uspešen prvi
test ne potrdi preostalih dveh poti. VPN mora omogočati povratni promet.
Pri ponovni povezavi 4G preveri obnovitev poti in dejansko svežino podatkov.

Ecowitt integracija uporablja podatke, ki jih konzola pošilja na naslov, pot in
vrata, prikazane v HA. Dokumentacija zahteva dostop prek HTTP; za oddaljeno
lokacijo naj ta promet potuje po zasebni VPN povezavi. W3001 ni izrecno naveden
med poročanimi prehodi na strani integracije, zato združljivosti ne sklepamo
iz imena. [Ecowitt v HA](https://www.home-assistant.io/integrations/ecowitt/).

## 2. Zemljevid fizičnih ventilov

Za vsak ventil dodaj vrstico; gredic ne združuj v en zapis GrowMaster.

| Ventil / fizični izhod | HA entiteta postaje | ID-ji in imena gredic | SI senzor trajanja | Vsota površin m² | Vsota pretokov L/min |
| --- | --- | --- | --- | --- | --- |
| dopolni | dejanski switch.* | dopolni | dejanski sensor.smart_irrigation_* | izračunaj | izmeri |

Na vseh gredicah istega skupnega ventila nastavi `mode=smart_irrigation`,
`valve_mode=shared`, isti `opensprinkler_station_entity` in isti
`smart_irrigation_entity`. SI cona mora pokrivati vse gredice tega ventila.
Identiteta, zgodovina in kulture ostanejo v GrowMaster. Prazna gredica na
skupnem ventilu trenutno blokira skupno samodejno zalivanje.

`flow_l_min` je pretok ene gredice, ne črpalke in ne cele cone. Mere, pretoki,
talni podatki in učinkovitost morajo ustrezati zahtevam skupnega ventila.
Če izpolniš vse tri podatke kapljičnih cevi, program iz njih izračuna in
prepiše `flow_l_min`; za neposredno izmerjeni pretok ta tri polja pusti prazna.
V `source` zapiši datum, tlak in način meritve. Nastavi izmeram prilagojena
`max_application_mm` in `max_run_seconds`; privzeta ura ni priporočeni odmerek.

## 3. Hidravlika

Znano: 20 L / 15 s × 60 = **80 L/min pri 2 bar na mestu meritve**.
Program za skupne ventile še uporablja konservativno mejo **75 L/min**.
Meritve črpalke ne vpisuj kot pretok vsake gredice.

Zabeleži mesto meritve glede na filter, regulator in glavni vod. Za vsako cono
izmeri tlak pri odprtem ventilu, celoten pretok ter enakomernost na začetku in
koncu kapljičnih cevi. Preveri dovoljeni tlak uporabljenih kapljačev.
Prvi preizkus naj uporablja en ventil naenkrat; preveri zaporedno izvajanje
in povezavo črpalke/master izhoda tudi v OpenSprinklerju.

Za kontrolo enot: `mm/min = pretok cone v L/min / površina cone v m²`.
Primer za računanje, ne nastavitev: dve gredici po 12 m² in 2 L/min pomenita
24 m², 4 L/min, 0,167 mm/min; v 6 minutah skupaj 24 L oziroma 1 mm bruto.
Dejanski izkoristek in izgube zahtevajo ločeno preverjanje.

## 4. Smart Irrigation in vreme

V HA odpri dejanski senzor trajanja. Spodaj so zahteve trenutne kode GrowMaster;
ne uveljavljaj jih s predlogo, ki bi skrivala manjkajoče ali zastarele podatke.

| Polje | Zahteva GrowMaster za skupno cono |
| --- | --- |
| stanje senzorja, `unit_of_measurement` | končno nenegativno trajanje, `seconds` |
| `size`, `size_unit` | vsota površin gredic; `m²` ali `m2` |
| `throughput`, `throughput_unit` | vsota pretokov; `l/min` ali `L/min` |
| `input_method` | nastavi `throughput`; neposredni padavinski pretok ni podprt na tej poti |
| `multiplier` | Kc iz aktualnih kultur in faz GrowMaster |
| `last_calculated` | čas s časovnim pasom, največ 6 ur star, ne v prihodnosti |

Po pošiljanju Kc mora slediti nov izračun z novejšim `last_calculated`.
Sprememba splošnega `last_updated` ni dokaz novega izračuna.
Dokumentacija SI opisuje površino, skupni pretok, Kc in čas izračuna med atributi
[senzorja cone](https://altmenorg.github.io/HAsmartirrigation/usage-entities.html).

Za W3001 popiši dejanske entitete temperature, vlage, padavin, vetra in sevanja,
njihove enote, čas zadnjega podatka in vir, ki ga uporablja SI. Ne enači
intenzivnosti dežja z dnevno količino. Manjkajočega senzorja ne nadomesti z ničlo.
Preveri vir podatkov SI tudi, če GrowMaster uspešno prikaže Ecowitt meritve:
bralni pregled GrowMaster teh vrednosti sam še ne vključuje v izračun bilance.
WH51 skupine in način `soil_sensor` se uvedejo po namestitvi in umerjanju.

## 5. Pregled brez odpiranja ventilov

V GrowMaster naj bo samodejno namakanje med pregledom izključeno. Status preveri
z `GET /api/irrigation/automatic-irrigation`; polje `enabled` mora biti `false`.
Polje `automatic_execution=false` v poročilu samo opisuje ta klic in ne potrjuje,
da je razporejevalnik izključen.

| Obstoječi klic GrowMaster | Kaj preveri |
| --- | --- |
| `POST /api/irrigation/home-assistant/test` | dostop strežnika GrowMaster do HA API; ne odpre ventilov |
| `GET /api/irrigation/home-assistant/states` | konfigurirane vremenske in talne entitete, enote in svežino |
| `GET /api/irrigation/profiles` | profile in `planning_conflicts` |
| `GET /api/irrigation/daily-readiness?day=YYYY-MM-DD` | današnjo pripravljenost gredic in skupin ventilov |
| `GET /api/irrigation/smart-irrigation?day=YYYY-MM-DD` | osnutke izvedbe ali razloge blokade |

Klici uporabljajo obstoječo prijavo GrowMaster. Za vreme bralni pregled uporablja
obstoječo nastavitev `HOME_ASSISTANT_WEATHER_ENTITIES`; prazna nastavitev pomeni,
da vremenske entitete niso zajete, ne da je vreme preverjeno. ID-je prepiši iz HA.

Pri pozitivnem trajanju pričakuj en izvedljiv osnutek na skupni ventil in vse
njegove ID-je gredic. Konflikt profila, različne razvojne faze, manjkajoč podatek
ali zastarel SI izračun morajo dati razlog blokade, ne izvedljivega ukaza.
Te negativne primere preveri na kopiji podatkov, ne z izmišljanjem meritev v živi evidenci.

## 6. Nadzorovani preizkus na lokaciji

Pred izvedbo preveri druge HA/SI avtomatizacije in lokalne OpenSprinkler programe:
isti ventil naj ima enega izvajalca, da se zalivanje ne podvoji. Za to integracijo
je zagon `opensprinkler.run_station`, ustavitev pa `opensprinkler.stop`;
stikalo omogoča postajo in ni ukaz za zagon.
[Dokumentacija integracije](https://github.com/vinteo/hass-opensprinkler#using-actions).

1. Na lokaciji potrdi fizični izhod in priključene gredice ter možnost lokalne
   ustavitve črpalke in ventila. Izberi kratek čas glede na izmerjeni pretok.
2. Sproži en pregledan ukaz. Zapiši zahtevani in dejanski začetek, konec, tlak,
   količino ter dejansko namočene gredice. Preveri izklop ventila in črpalke.
3. Preveri knjiženje dejansko dodane vode v SI bilanco natanko enkrat. Odgovor HTTP
   in stanje stikala sama ne dokazujeta pretoka; neuspešnega zagona ne knjiži kot vodo.
4. Preveri izpad VPN/HA ob prisotni osebi: obnašanje že zagnanega ventila in lokalni
   konec časa je treba izmeriti. GrowMaster ne sme biti edina možnost ustavitve.
5. Po negotovem odzivu najprej preveri dejansko stanje; ne ponavljaj kopiranega ukaza.
   Zaščita GrowMaster pred ponovitvijo ne pokriva ročnih ukazov ali drugih izvajalcev.

Avtomatiko vključi šele po potrjenem zemljevidu, pretokih, svežih podatkih,
knjiženju vode in preverjenem ustavljanju. Ta dokument ničesar ne vključi.

## Zapis rezultata

| Korak | Rezultat / meritev | Datum in izvajalec |
| --- | --- | --- |
| Različice, mrežne poti in 4G ponovna povezava | ni izvedeno | — |
| Zemljevid gredic, ventilov in SI con | ni izvedeno | — |
| Tlak, pretok in enakomernost posameznih con | ni izvedeno | — |
| Vreme, enote, svežina in Kc | ni izvedeno | — |
| Bralni pregled pripravljenosti | ni izvedeno | — |
| Zagon, konec, količina in SI knjiženje | ni izvedeno | — |
| Izpad povezave in lokalna ustavitev | ni izvedeno | — |
