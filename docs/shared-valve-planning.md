# Skupne fizične cone: načrt in prvi izvedbeni sklop

Osnova: GrowMaster 1.25.12, commit 1fdcf9288802a3484ecc70ad3162fdb9aa61ebea.
Datum: 18. oktober 2026.

## Dogovorjena arhitektura

- Na vrtu: samostojni OpenSprinkler v4, OpenWrt usmerjevalnik in 4G modem.
- Doma: Raspberry Pi s Home Assistantom, Smart Irrigation in integracijo OpenSprinkler.
- Povezava med lokacijama: VPN. Upravljanje ventilov ostaja prek obstoječe HA povezave.
- GrowMaster ostaja edini vir kultur, zasaditev, zgodovine in razvojnih faz.
- Fizična cona pomeni ventil, ki trajno oskrbuje eno ali več gredic. Gredice ohranijo ID in lasten kolobar.
- Projektna omejitev je 72 fizičnih con. WH51 skupina ni fizična cona.

Meritev uporabnika: 20 L v 15 s pri 2 bar = **80 L/min pri 2 bar na mestu meritve**.
Prvi sklop ohranja konservativno projektno mejo 75 L/min. To ni meritev pretoka na
koncu kapljičnih cevi ali dovoljenje za hkratno delovanje več con. Potrebni so še
podatki o mestu meritve, filtrih, izgubah cevovoda in kapljačih.
Ecowitt W3001 ostaja predvideni vremenski vir; dejanske HA entitete in podatkovni
tok niso bili preverjeni. WH51 še niso vgrajeni, zato jih ne obravnavamo kot meritve.

## Kaj obstaja in kaj manjka

`irrigation_routes.py` že vsebuje vodne profile, Kc po razvojnih fazah, HA povezavo,
Smart Irrigation pregled, OpenSprinkler osnutke in izrecno vključljivo avtomatiko.
Skupni ventil je predstavljen z enakim `opensprinkler_station_entity` na več profilih.
`valve_mode=shared` označuje skupno uporabo. Novega modela con za ta sklop ne potrebujemo.

`production_planner.py` je do sedaj preverjal sezono, razpoložljivost in zgodovino
kolobarja posamične gredice, brez drugih gredic istega ventila. To je glavna popravljena vrzel.

## Izvedeno

1. `irrigation_planning.py` prebere obstoječe profile iste kmetije in zgradi skupine
   po fizičnem ventilu. Preveri enake mere gredic, pretok, talne parametre in učinkovitost.
   V skupni pretok šteje tudi trenutno prazne gredice, saj se njihov ventil odpira skupaj.
2. Za sočasno zasedene gredice preveri Kc vsak dan skozi celotno prekrivanje do
   ocenjene sprostitve. Uporabi napoved začetka pobiranja in obstoječe meje faz 20/80 %;
   pri presajankah šteje od presajanja na gredico. Preveri tudi produkt globine korenin
   in dovoljenega deleža izčrpanja. Manjkajoči podatki niso dovoljenje za združevanje.
3. Proizvodni predlogi vključujejo obstoječe načrte, aktivne zasaditve in že izbrane
   predloge sosednjih gredic. Za vsako sorto poiščejo prvi ustrezen datum z dnevnim
   zamikanjem znotraj izbranega obdobja. Vsak zamik znova preveri kolobar in sezono.
4. Ročno shranjevanje preko `POST /api/plans` preveri skupni ventil pred zapisom.
   Nezdružljiv načrt vrne 422; prekinjena serija se ne shrani delno.
5. Shranjevanje profila gredice zavrne 73. različni ventil, dovoljuje pa več gredic
   na istem ventilu. Obstoječi podatki se ne prepisujejo ali samodejno preslikujejo.
6. Vmesnik proizvodnih predlogov prikaže razloge za izločitev in potreben zamik.

## Meje tega sklopa

To je konservativno preverjanje združljivosti po profilih, ne napoved dejanske
vode v tleh. Enak Kc je potreben približek, ni dokaz enakega trenutnega primanjkljaja.
Kc in vodni prag se morata ujemati z numerično toleranco 0,001; to ni agronomska
toleranca stresa. Model še ne vključuje vremenske napovedi, različnih začetnih
primanjkljajev, negotovosti DTM ali namernega zmernega pod-/prezalivanja.

Algoritem ostaja determinističen lokalni izbor po gredicah, brez globalnega iskanja
vseh kombinacij ali vračanja na predhodne izbire. Lahko izpusti kombinacijo, ki bi
jo našla globalna optimizacija. Poljuben začetni neuspeh obstoječega sezonskega ali
kolobarnega filtra se ne rešuje z dodatnim iskanjem; zamike išče po vodnem konfliktu.

Spremembe vodnih profilov in potrjevanje naučenih popravkov DTM še ne preverjajo
vseh že shranjenih načrtov. Premiki nasledstva, zamiki, zaključki zasedenosti ter
aktivacija in neposredna setev so vključeni v tretji sklop spodaj. Avtomatika ni
bila preverjena na fizični opremi.

## Drugi sklop: ena Smart Irrigation cona na fizični ventil

Vse gredice skupnega ventila nastavite na `smart_irrigation`, `valve_mode=shared`,
isti OpenSprinkler switch in isti SI senzor. V Home Assistantu ročno nastavite
skupno površino in vsoto pretokov. GrowMaster nastavitve primerja z atributi `size`
in `throughput`; zahteva metrične enote `m²`/`m2` ter `l/min`/`L/min` in način
izračuna iz pretoka. Manjkajoče enote ali nepodprta različica pomenijo blokado.

- Vse fizično povezane gredice morajo imeti aktivno zasaditev in primerljive profile.
  Različni trenutni Kc, prazna gredica ali senzor, ki pokriva več ventilov, blokirajo cono.
- Dnevni pregled senzor prebere enkrat; ne zahteva dodatnih ročnih dnevnih bilanc.
  SI rezultat ostaja izračun Home Assistanta. GrowMaster ne kliče dodatnega preračuna.
- Predogled in pošiljanje pripravita en Kc na skupno cono. Po spremembi Kc mora biti
  `last_calculated` novejši od oddaje Kc, tudi pri ročni posodobitvi brez avtomatike.
  `last_updated` sam ne potrjuje novega izračuna skupne cone.
- Čas ventila ni vsota časov gredic. Uporabi en SI čas, omejen z najstrožjim največjim
  odmerkom in časom posamezne gredice. Litri se ocenijo ločeno po vejah in seštejejo.
- Samodejni zagon ostaja izrecno vključljiv in zabeleži namero pred klicem HA.
  Pri negotovem odzivu istega ventila isti dan ne pošlje znova. To ni potrditev pretoka.
  Ročno kopiranje osnutka v HA nima te zaščite pred ponavljanjem.
- Stara pot z ločenimi SI senzorji na skupnem ventilu ostaja združljiva in še zahteva
  ločene dnevne bilance. Priporočena nova konfiguracija uporablja en senzor na ventil.

Potrditev dejansko izvedenega zalivanja in knjiženje vode v SI bilanco ostajata
odgovornost HA izvedbene avtomatike. HTTP uspeh ne sme samodejno ničliti primanjkljaja.
Pred uporabo je treba preveriti nameščeno SI različico, izgube in umerjanje sistema.

## Tretji sklop: nasledstvo in aktivacija

- Pregled nasledstva izloči namakalno nezdružljive ciljne gredice in blokira
  predlagan zamik, če nove razvojne faze ne ustrezajo drugim gredicam istega ventila.
  Pregled ne spreminja zapisov v podatkovni bazi.
- Žeton predloga vključuje tudi vodne profile gredic in kultur. Po njihovi spremembi
  je treba pregled osvežiti; prej odprtega predloga ni mogoče potrditi.
- Premik, potrditev zamikov in sprememba zaključka zasedenosti ponovno preverijo
  skupni ventil pred zapisom. Pri konfliktu se transakcija razveljavi.
- Aktivacija načrta in neposredna setev preverita dejanski zapis nove zasaditve
  pred spremembo stanja gredice in ustvarjanjem opravil. Obstoječe preverjanje
  kolobarja ostane veljavno; njegov ročni obhod ne obide namakalne združljivosti.

## Naslednji implementacijski koraki

1. Isti validator vključiti še v potrjene popravke napovedi DTM in spremembe vodnih
   profilov ter opozarjanje na prizadete obstoječe načrte. Preveriti še vse ostale
   poti priporočil, ki niso proizvodni načrtovalnik ali pregled nasledstva.
2. Na dejanski HA namestitvi preveriti skupni senzor, enote, `last_calculated` in
   knjiženje dejansko izvedenega zalivanja v SI bilanco. Programsko združevanje je izvedeno.
3. Uvesti shranjene meritve hidravlike in omejitev vira namesto projektne konstante;
   umeriti mm/min vsake cone pri delovnem tlaku. Preveriti zaporedno izvajanje,
   črpalko/master izhod in seštevek pretokov pri morebitnem sočasnem odpiranju.
4. Preveriti konkretne W3001 entitete, enote in svežino prek HA/VPN. Dodati simulacijo
   vodne bilance po gredicah za izbrano vremensko napoved; meritev WH51 dodati šele
   po vgradnji in umerjanju. Nedokončana lokalna simulacija iz drugega klepeta je ohranjena.
5. Šele z validiranimi agronomskimi tolerancami razširiti izbiro na skupno optimizacijo
   kulture, sorte in datuma: najprej izvedljivost/kolobar, nato vodni stres, poraba vode
   in pridelovalni cilji. Ob nedosegljivi ali zastareli telemetriji zahtevati pregled.

## Preverjanje in viri

Po tretjem sklopu: 329 zalednih testov uspešnih (20 testov skupne SI cone in 10 novih
testov sprememb nasledstva ter aktivacije),
produkcijska gradnja vmesnika uspešna. Gradnja uporablja obstoječe lokalne odvisnosti
in opozori na paket nad 500 kB. Fizična oprema in dejanska HA namestitev nista bili testirani.

Regresijski sklop: `python -m pytest tests/test_irrigation_planning.py
tests/test_production_planner.py tests/test_irrigation.py tests/test_shared_smart_irrigation.py tests/test_shared_irrigation_mutations.py tests/test_succession.py -q`
iz mape `backend`. Testi uporabljajo SQLite in nadomestne HA odzive; ne odpirajo ventilov.

- [OpenSprinkler: največ 72 con](https://opensprinkler.com/product/opensprinkler/)
- [Home Assistant Ecowitt](https://www.home-assistant.io/integrations/ecowitt/)
- [Smart Irrigation storitve](https://altmenorg.github.io/HAsmartirrigation/usage-services.html)
- [Smart Irrigation atributi con](https://altmenorg.github.io/HAsmartirrigation/usage-entities.html)

Dokumentacija potrjuje splošne možnosti integracij. Nameščene različice HA,
Smart Irrigation in OpenSprinkler ter W3001 združljivost na tej lokaciji niso preverjene.
