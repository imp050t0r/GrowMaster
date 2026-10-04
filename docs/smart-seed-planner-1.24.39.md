# GrowMaster 1.24.39 — Smart Seed Planner

V zavihku **Plan** je pod tedensko napovedjo dela nov **Načrtovalnik semena**. Uporablja obdobje koledarja in združi potrebe neposrednih setev po kulturi in sorti, z obstoječo 5 % rezervo.

- Odpravljena napačen parameter in ključ rezultata, ki sta prekinila obstoječo napoved semena.
- Norma sorte ima prednost pred standardnim sejalnim profilom.
- Zaloga iste sorte se razporedi po terminih setev in najbližjem roku uporabnosti. Rok na dan setve je še veljaven. Pretečena preostala zaloga ne pokriva poznejših potreb.
- Prikazani so termin prvega primanjkljaja, potrebe posameznih gred in predlog števila pakiranj. Brez velikosti pakiranja ni izmišljenega predloga.
- Pretvorba števila semen v grame zahteva maso tisoč semen; obloženo seme se ne pretvarja v grame. Neveljavni podatki so izločeni z opozorilom; manjkajoč rok uporabnosti je posebej označen.

To je začetna različica za neposredne setve. Pri presajanih načrtih izračun še ni na voljo: zahteva število sadik, kalivost in izgube v vzgoji. Takšni načrti so vidno označeni in niso vključeni v vsoto. Napoved ni nakup, rezervacija ali odpis; ne upošteva drugih rezervacij zaloge. Predlog pakiranja temelji na najmanjšem vpisanem pakiranju serij sorte, ne na trenutni ponudbi dobavitelja.

Obstoječe funkcije uporabljajo isti endpoint. Baza in zaloga se pri pregledu ne spreminjata. Nova migracija, odvisnost ali storitev ni potrebna.

Preverjanje: 119 backend testov, 18 frontend testov, uspešna produkcijska gradnja in pregled UI na ločeni testni bazi. Namestitev na dejansko aplikacijo še ni izvedena.

Naslednja faza potrjene razvojne poti: **1.24.40 — Harvest Forecast**.
