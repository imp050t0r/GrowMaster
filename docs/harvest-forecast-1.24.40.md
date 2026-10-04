# GrowMaster 1.24.40 — Harvest Forecast

V zavihku **Plan** je pod načrtovalnikom semena nov **Tedenski pregled žetve** oziroma **Tedenska napoved žetve**. Uporablja isto obdobje koledarja kot napoved dela in semena.

Pregled prikaže shranjena okna Dynamic DTM ter sredinski datum prve žetve. Če napoved manjka, je neveljavna ali se nanaša na drug termin setve/presajanja, uporabi obstoječi načrtovani datum in pojasni omejitev. Za nazaj ne ustvarja nove napovedi. Potekla okna so označena in se ne premikajo samodejno.

Načrtovane setve in aktivne zasaditve so vključene. Aktiviran načrt se ne šteje še enkrat; količino povežemo z aktivno zasaditvijo samo pri eni nedvoumni povezavi iste kulture, sorte, grede in datuma setve. Zasaditev z že zabeleženim pobiranjem ni prihodnja prva žetev. Prihodnji zapisi pobiranja ne veljajo kot dejanska žetev.

Tedenske količine so **vnesene ocene**, ne model napovedovanja biološkega pridelka. Posamezna količina je razporejena enkrat, po sredinskem datumu. Število oken, ki segajo v teden, se prikazuje posebej; teh števil ne seštevamo, ker lahko eno okno sega v več tednov. Če sredinski datum leži zunaj izbranega obdobja, ostane prekrivajoče okno vidno med pojasnili, količina pa ni umetno prestavljena v izbrani teden.

Pri sortah, ki podpirajo večkratno pobiranje, ne predpostavljamo razdelitve celotnega pridelka po rezih. Vnesena količina za cikel ostane vidna, tedenska količina pa je neznana. Priprava razporeda ponovljenih pobiranj ostaja omejitev te začetne različice. Pri neznani ali neveljavni količini ne prikazujemo ničle kot ocene.

Ločeno so sešteta dejansko zabeležena pobiranja v izbranem obdobju do današnjega dne, brez odpada. Vključena so tudi pobiranja zaključenih kultur. Ta vsota ni zaloga za prodajo in ni neposredno primerljiva z delno napovedjo prvih žetev. Obstoječa napoved ponudbe/povpraševanja ostaja nespremenjena.

Endpoint: `GET /api/planning/harvest-forecast?start=YYYY-MM-DD&end=YYYY-MM-DD`. Obdobje je vključujoče in dolgo največ 367 dni. Podatki so omejeni na obstoječo kmetijo 1, enako kot drugi načrtovalni pogledi. Pregled je samo bralen: ne spreminja načrtov, DTM, datumov, žetev ali zaloge.

Nova migracija, odvisnost ali nastavitev ni potrebna. Shema ostaja `0015_bed_release_date`. Preverjeno: **137 backend testov, 18 frontend testov, produkcijska gradnja in pregled dejanske UI-komponente na ločeni testni bazi**. Windows in Android izdajo izdeluje obstoječi GitHub postopek.

Naslednja faza potrjenega načrta: **1.25.0 — AI Production Planner**.
