# GrowMaster 1.25.3 — Priprava akcij OpenSprinkler za Home Assistant

V **Plan → Namakanje → Profil grede** sta novi polji: **Postaja OpenSprinkler v Home Assistantu** (entity ID stikala postaje, npr. `switch.greda_1_station_enabled`) in **Največji čas postaje (sekunde)** (privzeto 3600). Pretok velja za eno gredico. Prazna postaja pomeni, da greda ni povezana.

Po spremembi profila ga shrani, preveri dnevne podatke ter izberi **IZRAČUNAJ IN SHRANI DAN**. Nato **PRIPRAVI AKCIJE OPENSPRINKLER** pripravi osnutke iz vseh shranjenih izračunov izbranega dneva. Za uspešno pripravo zahteva:

- današnji izračun največ šest ur star, brez prihodnjega časa;
- nespremenjena shranjena profila kulture/grede in površino;
- aktualno ponovno preverjanje ročne meritve WH52, kadar je vključena;
- rezultat bilance `irrigate`, veljaven pretok in postajo;
- pozitivno trajanje, zaokroženo navzgor na sekundo, največ do nastavljene omejitve;
- postajo, povezano samo z eno gredico na kmetiji; skupne cone niso podprte.

Ob neizpolnjenih pogojih prikaže razloge brez akcije. Profil iz 1.25.2 ostane združljiv: postaja je prazna, največji čas 3600 sekund. Migracija baze ni potrebna; novi parametri so v obstoječem profilu.

Osnutek uporablja dokumentirano akcijo `opensprinkler.run_station`, ciljni entity ID, `run_seconds` in `queue_option: append`. Stikalo postaje je cilj akcije; `switch.turn_on` ni ukaz za zagon. [Dokumentacija uporabljene integracije](https://github.com/vinteo/hass-opensprinkler#using-actions).

Po preverjanju dejanske postaje, dežja, stanja tal in že izvedenega namakanja lahko zapis ročno uporabiš v Home Assistantu **Orodja za razvijalce → Akcije → YAML**. Izvedba tam dejansko odpre ventil. GrowMaster akcij ne pošilja, ne preverja dosegljivosti HA ali stanja postaj in ne shranjuje HA/OpenSprinkler poverilnic. Izračuni in osnutki niso potrdilo izvedbe. Osnutka ne ponavljaj samodejno: še ni evidence izvedbe oziroma zaščite pred ponovljenim zagonom. Nastavitve OpenSprinklerjevih programov in drugih avtomatizacij preveri, da ne podvojijo zalivanja.

Podprta je dokumentirana integracija `vinteo/hass-opensprinkler`; njene namestitve na uporabnikovem Home Assistantu ta izdaja ne preveri. Novi samo bralni endpoint `GET /api/irrigation/opensprinkler?day=YYYY-MM-DD` vrne `requires_manual_review: true`, `automatic_execution: false`, vrstice z osnutkom ali razlogi blokade. Uporablja obstoječo prijavo in omejitev kmetije 1. Ne predstavlja avtomatizirane povezave Home Assistant–GrowMaster.

Preverjeno: **242 backend testi, 18 frontend testov, produkcijska gradnja in UI shranjevanje povezave postaje/priprava akcije/razveljavitev ob spremembi vhodov** na ločenih testnih podatkih. Dejanski ventili niso bili aktivirani.

Za naslednji korak priklopa potrebujemo potrditev namestitve integracije v HA, entity ID-je postaj in njihove gredice oziroma cone, model Ecowitt prehoda in razpoložljive vremenske/WH52 meritve. Gesel ali žetonov ne pošiljaj v pogovor. Samodejni zajem vremena, dnevni razporejevalnik in samodejna izvedba še niso vključeni.
