# GrowMaster 1.24.36 – napovedana in dejanska žetev

V zavihku Plan, pod pregledom sukcesij, je nov razdelek Napovedana in dejanska žetev. Primerja začetni shranjeni posnetek napovedi s prvim zabeleženim pobiranjem. Prikaže prvotni načrt, napovedani interval, odmik v dnevih, število pobiranj in ločen datum zaključka kulture. Pozitiven odmik pomeni poznejšo žetev.

Povprečna absolutna napaka vključuje samo primerne zapise. Manjkajoči ali neveljavni posnetki, manjkajoča pobiranja, časovno neveljavni datumi ter napovedi, nastale na dan žetve ali pozneje, niso vključeni. Pri vsakem izključenem zapisu je razlog. Za zgodovinske zasaditve se napovedi ne ustvarjajo za nazaj. Poznejši izračun ne nadomesti začetne napovedi.

Prvo zabeleženo pobiranje je približek zrelosti, ne biološka meritev: nanj vplivajo odločitve pri delu in popolnost evidence. Prikazano število dni se nanaša na prvotni referenčni datum napovedi, ki se lahko razlikuje od pozneje prestavljenega načrta. Večkratno pobiranje ne šteje kot več neodvisnih primerov točnosti.

Izdaja ne spreminja datumov, DTM ali pravil napovedovanja. Samodejno učenje še ni vključeno. Novih odvisnosti in migracije ni; shema ostaja 0015_bed_release_date. Podatki za pregled že obstajajo v zasaditvah, začetnih posnetkih napovedi in evidenci žetve.

Preverjeno: 84 backend testov, 18 frontend testov, produkcijska gradnja ter prikaz resničnega API-odziva na ločeni testni bazi v brskalniku. Testi vključujejo izolacijo kmetije, odsotnost zapisovanja, ponovljena pobiranja, meje intervala, prvotni posnetek in izključitev napovedi za nazaj. Obstoječa opozorila o zastarelih knjižničnih vmesnikih in velikosti frontend paketa ostajajo.

Namestitev: ob delujočem Docker Desktop zaženi GrowMaster-Setup-1.24.36.exe in ohrani dosedanjo mapo podatkov. Nato preveri različico 1.24.36 in odpri Plan. Paket je pripravljen, ni samodejno nameščen. Zagon nadgradnje Dockerja iz tega razvojnega okolja je omejen.
