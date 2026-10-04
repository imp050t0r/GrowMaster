# GrowMaster 1.25.2 — Namakanje (začetna ročna različica)

V **Plan → Namakanje** izberi kulturo in gredico. Najprej shrani profil kulture (Kc za začetno, polno in pozno fazo, trenutna učinkovita globina korenin, dovoljeni delež izsušitve in vir) ter profil grede (poljska kapaciteta in točka venenja kot volumenska odstotka, učinkovitost, največji enkratni odmerek, po želji pretok grede in umerjena praga WH52).

Profili niso samodejno napolnjeni z univerzalnimi vrednostmi. Preveri jih za svojo kulturo, fazo, zemljo in način pridelave. Izbira kulture ne preverja dejanske zasaditve; modul je uporaben tudi za ročni pregled scenarijev.

Dnevni vnos zahteva današnji ali pretekli datum, fazo rasti, potrjen začetni primanjkljaj v mm, učinkoviti dež, že izvedeni bruto odmerek namakanja in vir podatkov. ET₀ je dnevna referenčna evapotranspiracija; prazna vrednost pomeni manjkajoč podatek, ne ničelne porabe. Pod streho učinkoviti dež ni enak dežju zunanje postaje.

Izračun uporablja:

- `ETc = ET₀ × Kc`.
- `TAW = 1000 × (poljska kapaciteta − točka venenja) × globina korenin`, deleža vode sta med 0 in 1.
- `RAW = TAW × dovoljeni delež izsušitve` (ročno izbran nespremenljiv delež).
- Primanjkljaj = začetni primanjkljaj + ETc − učinkoviti dež − izvedeno namakanje × učinkovitost; omejen na 0 do TAW.
- Ob doseženem pragu RAW predlaga dopolnitev primanjkljaja, popravljeno za učinkovitost in omejeno z največjim enkratnim bruto odmerkom.
- `litri = bruto mm × površina m²`; čas samo ob znanem pretoku za to gredico.

Osnova: [FAO 56, vodna bilanca korenin](https://www.fao.org/4/x0490e/x0490e0e.htm) in [ETc](https://www.fao.org/4/x0490e/x0490e0a.htm). To je poenostavljena ocena s stalnim Kc za izbrano fazo: brez izračuna ET₀ iz surovih vremenskih meritev, kapilarnega dotoka, samodejnega razvoja korenin, koeficienta stresa ali modela odtoka. Ob preseženi kapaciteti opozori na možen stres. Ročne ocene so označene z nizko zanesljivostjo, brez izmišljenega odstotka točnosti.

WH52 je neobvezno ročno preverjanje. Odstotka WH52 ne pretvarja neposredno v litre. Zahteva oba umerjena praga, čas s časovnim pasom in današnjo meritev največ šest ur staro. Pri zastareli/prihodnji meritvi, manjkajočih pragovih ali neskladju z bilanco vrne **Potreben pregled**, brez priporočene količine. Brez WH52 je rezultat izrecno samo ocena bilance.

**IZRAČUNAJ NAMAKANJE** ne zapisuje podatkov. **IZRAČUNAJ IN SHRANI DAN** shrani posnetek vhodov, profilov, rezultata in časa izračuna; isti dan in gredica nadomestita prejšnji posnetek. Shranjeno priporočilo ni izvedeno zalivanje in se ne odšteje od bilance. Začetni primanjkljaj vsak dan potrdi sam; podatki se ne prenašajo med dnevi in manjkajoči dnevi se ne ugibajo. Posnetki se ob spremembi profilov ne preračunajo.

API pod `/api/irrigation`: `GET /profiles`, `PUT /crops/{id}`, `PUT /beds/{id}`, `POST /calculate`, `PUT /daily`, `GET /daily?day=YYYY-MM-DD`. Uporablja obstoječo prijavo in licenčne omejitve. Gredice, profili in poročila so omejeni na obstoječo kmetijo 1.

Migracija **0016_irrigation** doda tri ločene tabele brez spremembe podatkov kultur, gredic ali zasaditev. Obstoječe varnostne kopije brez novih tabel je mogoče obnoviti; namakalni podatki so pri takšni obnovitvi prazni. Nove kopije vključujejo profile in poročila. Preverjeno na ločeni SQLite bazi: ponovljiva migracija, ohranitev gredic ter obnovitev novih in starih kopij.

Preverjeno: **223 backend testi, 18 frontend testov, produkcijska gradnja in UI izračun/shranjevanje/sprememba profila**.

**Vremenska postaja, WH52 in Home Assistant še niso samodejno povezani.** Ni dnevnega razporejevalnika, skupnih con ali upravljanja ventilov. Naslednji korak je priklop dejanskih meritev in preverjanje priporočil: potrebujemo model Ecowitt prehoda, razpoložljive meritve/entity ID-je v Home Assistantu ter razpored senzorjev in namakalnih con. Ta izdaja ne vsebuje poverilnic ali nove zunanje storitve.
