# GrowMaster 1.25.0 — AI Production Planner (začetna lokalna različica)

V zavihku **Plan** je nov **Predlog pridelave**. Izberi prihodnje obdobje, do 10 kultur in največ 100 novih gredic ter klikni **PRIPRAVI PREDLOG**. Obdobje je skupno z obstoječim koledarjem in napovedmi.

Ta začetna različica uporablja lokalna pravila in podatke GrowMasterja, **ne zunanjega AI modela**. Ponovno uporabi pravila kolobarja, sezonsko primernost, razvrščanje kultur in Dynamic DTM. Brez nove storitve, ključa, odvisnosti ali prenosa kmetijskih podatkov tretjim osebam.

- Na gredico predlaga največ eno novo kulturo. Izbrane kulture razporeja čim bolj enakomerno med ustrezne gredice; znotraj tega izbira po obstoječem ocenjevanju, datumu in stabilnih identifikatorjih. To ni globalna optimizacija ali razpored vseh sukcesij.
- Uporablja samo gredice s stanjem `empty`, brez aktivne zasaditve. Aktivnih kultur ne zaključuje samodejno. Že načrtovane kulture so upoštevane kot zasedenost in kolobarska omejitev.
- Preveri zadnje cikle oziroma zadnjo družino grede ter družine že načrtovanih naslednjih kultur. Če podatki o zgodovini manjkajo, to posebej označi.
- Po potrebi prestavi novo setev za konec znane zasedenosti; celotno ocenjeno okno prve žetve mora stati znotraj izbranega obdobja. Neznana sprostitev obstoječega načrta pomeni neznano zasedenost od začetka tega načrta.
- Za sadike zahteva vpisan čas vzgoje. Setev in presajanje sta ločena; DTM ima referenco na presajanje. Način vzgoje mora biti določen v podatkih sorte.
- Sorte, ki podpirajo večkratno pobiranje, so izločene iz samodejnih novih predlogov: prva žetev ne določa konca zasedenosti.
- DTM je sezonska ocena brez samodejnega vremenskega ali učnega popravka. Predlog ne potrjuje primerne temperature, dovolj semena, razpoložljivih ur ali doseganja prodajnih količin.

**PRENESI V OBRAZEC** izpolni obstoječi obrazec setve. Ne ustvari ali spremeni načrta. Pričakovani kilogrami ostanejo prazni: vnesi svojo oceno, preveri datume in pogoje ter šele nato klikni **DODAJ V NAČRT**. Shranjevanje uporablja obstoječe opozorilne in potrditvene postopke; predlog ni rezervacija gredice. Ob spremembi obdobja, izbire kultur ali osvežitvi podatkov se predlog razveljavi. Obstoječi načrti in podatki ostanejo nespremenjeni.

API: `POST /api/planning/production-proposals` s polji `start`, `end`, `crop_ids`, `max_beds`. Samo bralen izračun; prihodnje vključujoče obdobje do 367 dni. Podatki gred in zasaditev so omejeni na obstoječo kmetijo 1, kot pri drugih načrtovalnih pogledih.

Shema ostaja `0015_bed_release_date`; migracija ni potrebna. Preverjeno: **161 backend testov, 18 frontend testov, produkcijska gradnja in UI priprava/pregled/prenos predloga na ločenih testnih podatkih**. Windows in Android paketa izdeluje obstoječi GitHub postopek.
