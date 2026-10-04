# GrowMaster 1.24.34 – začetni Dynamic DTM

Osnova: GitHub `imp050t0r/GrowMaster`, oznaka `v1.24.33`, revizija
`e6acfa2886a792050509dfdf28bcdf2a60e9e5b3`.

## Obnašanje

- Katalog `days_to_harvest` in štiri sezonske vrednosti ostanejo nespremenjeni.
- Ob ustvarjanju zasaditve ali načrta se shrani ločena dinamična napoved.
- Obstoječi `expected_harvest_date`, opravila in sukcesije se ne prestavljajo.
- Vmesnik pri setvah in načrtih pokaže katalog, dinamično število dni, referenčni
  datum, okvir žetve, kakovost vhodnih podatkov in razlago.
- Stari zapisi po migraciji nimajo izmišljene zgodovinske napovedi. Uporabnik lahko
  za odprt zapis izbere **IZRAČUNAJ OCENO**.
- Aktivacija načrta prenese napoved in prvotni posnetek; datum presajanja ostane
  referenca tudi pri kasnejšem preračunu. Pri starejših aktivacijah se prebere
  povezani načrt, če obstaja.

## Izračun in omejitve

Privzeto se uporabi obstoječa sezonska ocena iz `maturity.py`. Njene štiri vrednosti
lahko izvirajo iz stare samodejne ocene; niso predstavljene kot lokalna kalibracija.

GDD je mogoče uporabiti z izrecno podanimi dnevno povprečnimi temperaturami v °C,
bazno temperaturo, ciljno vsoto GDD in navedbo vira podatkov ter umerjanja.
Dnevni prispevek je `max(0, mean_c - base_temperature_c)`. Potreben je neprekinjen
niz od referenčnega dne do doseženega cilja, največ 730 dni. Vsak vnos predstavlja
celoten dnevni interval; rezultat je število končanih intervalov od reference.
Manjkajočih dni se ne zapolnjuje, kratke vremenske napovedi se ne podaljšujejo z
zadnjo temperaturo. Če cilj ni dosežen, se uporabi sezonska ocena z razlago.
GDD nadomesti sezonski popravek, zato ni dvojnega upoštevanja sezone.

Vir osnovne metode: [University of Minnesota Extension – Using growing degree
days to plan early-season alfalfa harvests](https://extension.umn.edu/agriculture/crop-production/forages/using-growing-degree-days-to-plan-early-season-alfalfa-harvests).
Pragov lucerne ali drugih kultur ta izdaja ne prenaša na zelenjadnice.

Vremenska postaja in ponudnik vremenske napovedi še nista povezana. Fotoperiodni
popravek se ne izvaja, ker ni podatkov o umerjenem odzivu sorte. Ni privzetih
popravkov za rastlinjak, toploto tal ali namakanje.

`low` in `medium` sta oznaki kakovosti podatkov, ne statistični verjetnosti.
Okvir žetve je hevrističen: ±25 % dni za nizko in ±15 % za srednjo kakovost,
najmanj ±2 dni; spodnja meja ne sega pred prvi dan po referenci. To ni umerjen
interval zaupanja. Srednja oznaka je dovoljena le ob doseženem GDD cilju s samimi
izmerjenimi temperaturami; napovedi in klimatologija ostanejo nizko ocenjene.

## Podatki in prihodnje učenje

Migracija `0014_dynamic_dtm` v tabeli `plantings` in `crop_plans` doda nullable polja:
`dynamic_dtm_days`, `dynamic_dtm_confidence`, `predicted_harvest_start`,
`predicted_harvest_end`, `dynamic_dtm_explanation`, `dynamic_dtm_initial_snapshot`.

Razlaga vsebuje verzijo modela, vhodne podatke, katalog ob izračunu, referenco,
prvotno načrtovani datum, razloge in čas izračuna. Prvi posnetek se ob osvežitvi
ne prepiše. Dejanske žetve že obstajajo v `Harvest`, povezane s `planting_id`,
zaključek cikla pa v `Planting.completed_on`. To omogoča prihodnjo primerjavo;
samodejno učenje DTM v tej izdaji še ni vključeno. Datum zaključka ni obravnavan
kot datum prve žetve.

Izvoz varnostne kopije vključi nova polja. Uvoz stare kopije 1.24.33 jih dopolni
z `null`. Za vrnitev na staro izdajo je potrebna predhodna varnostna kopija baze;
samodejna odstranitev novih stolpcev ni del nadgradnje.

## API

`POST /api/plantings/{id}/dynamic-dtm` ali `POST /api/plans/{id}/dynamic-dtm`:
prazen JSON objekt izračuna sezonsko oceno. Odgovor vsebuje `dynamic_dtm`.
Pot uporablja obstoječo avtentikacijo in licenčno zaščito aplikacije.

Primer vhodne oblike (parametri in meritve so zgolj testni, ne priporočilo za kulturo):

```json
{
  "source": "Testna postaja",
  "calibration_source": "Testni parametri",
  "base_temperature_c": 5,
  "target_gdd": 100,
  "temperatures": [
    {"day": "2026-05-01", "mean_c": 15, "kind": "observed"}
  ]
}
```

Ta kratek primer se vrne na sezonsko oceno, saj ne doseže cilja. Dovoljene vrste
vnosov so `observed`, `forecast`, `climatology`; prihodnjih dni ni mogoče označiti
kot izmerjene. Podvojeni datumi, neveljavne temperature in neznana polja so zavrnjeni.

## Preverjanje

- Celoten backend: 56 uspešnih testov na SQLite, vključno z 12 novimi testi.
- Po popravku starih aktivacij: ponovno uspešnih 13 testov izračuna in API poteka.
- Frontend: 18 uspešnih obstoječih testov in uspešna produkcijska gradnja.
- Preverjena usklajenost različic backend/frontend/installer na 1.24.34.
- Brskalniški pregled ločene komponente s testnimi podatki: prikaz, razlaga,
  prazno stanje in sporočilo ob nedosegljivem API-ju.
- Migracija preizkušena na stari SQLite shemi, dvakrat zapored; stare vrednosti ostanejo.
- PostgreSQL 16.15: prehod iz prave sheme 1.24.33, ponovljena migracija in sveža
  baza so uspešni. Primerjava vseh prvotnih stolpcev in vrstic potrdi ohranitev
  podatkov; uspešni so tudi posnetki napovedi, referenca presajanja ter izvoz in
  obnova varnostne kopije z dejansko žetvijo. Preizkus je tekel na ločeni začasni
  instanci na localhost, brez dostopa do produkcijske baze.
- Zagonske skripte imajo veljavno sintakso; test prestavljanja podatkov pod
  Windows PowerShell 5.1 je uspešen.
- Docker slike v tem okolju niso bile zagnane: dostop do Dockerjevega vmesnika je zavrnjen.
- Lokalna nameščena aplikacija, produkcijska baza in oddaljeni GitHub niso bili spremenjeni.

Paket vsebuje izvorno kodo za pregled in gradnjo, ne nameščene posodobitve.
