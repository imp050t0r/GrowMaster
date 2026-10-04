# GrowMaster 1.24.35 – dinamične sukcesije

Načrtovanje prikazuje časovne konflikte med kulturami na isti gredi. Predlaga premik prihodnjih setev, presajanj in načrtovanih žetev ter ohrani trajanje vzgoje sadik. Spremembe se shranijo šele ob izbiri predloga. Zastarel predlog strežnik zavrne in zahteva osvežitev.

Pri enkratni žetvi uporabi poznejši datum med načrtovano žetvijo in koncem Dynamic DTM okna. Pri večkratnem pobiranju zahteva ročni zadnji dan zasedenosti. Naslednja kultura lahko zasede gredo naslednji dan. Setev danes ali v preteklosti prepreči samodejni premik. Alternativa je prazna, nenačrtovana greda enakih mer, preverjena glede zgodovine kolobarja.

Migracija 0015 doda nullable expected_bed_release_date zasaditvam in načrtom. Obstoječe vrednosti ostanejo nespremenjene. Aktiviranje načrta prenese ta datum. Varnostne kopije ga vključujejo; stare kopije brez njega ostanejo združljive. Kataloški DTM in začetni posnetek napovedi se ohranita.

Preverjanje: 68 backend testov, 18 frontend testov, produkcijska gradnja frontend; PostgreSQL 16.15 nadgradnja iz 0014, ponovna migracija, nespremenjeni obstoječi podatki, nova baza in obnova kopije. V brskalniku preverjen dejanski premik dveh načrtov prek novega vmesnika na ločenih testnih podatkih.

Namestitev: zaženi GrowMaster-Setup-1.24.35.exe ob delujočem Docker Desktop. Ohrani dosedanjo mapo podatkov. Po zaključku preveri različico 1.24.35 in v Načrtovanju razdelek Zaporedje kultur in konflikti. Paket je pripravljen; delujoča namestitev s tem preverjanjem ni bila nadgrajena. Nadgradnja Docker namestitve v tem okolju ni bila preverjena zaradi omejenega dostopa do Dockerja.

Omejitve: napoved ostaja ocena. Večkratna žetev brez zaključnega datuma ne dovoljuje zanesljivega samodejnega razporejanja. Premik lahko pokaže sezonsko opozorilo; uporabnik presodi primernost termina. Ta izdaja ne uvaja samodejnega učenja ali novih vremenskih storitev.
