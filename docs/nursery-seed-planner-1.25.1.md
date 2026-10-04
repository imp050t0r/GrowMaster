# GrowMaster 1.25.1 — Seme za sadike

V zavihku **Plan**, pod **Načrtovalnikom semena**, je nov izračun **Seme za sadike**. Izberi prihodnji načrt presajanja v obdobju koledarja ter vnesi potrebno število uporabnih sadik, kalivost semena, pričakovani delež uporabnih sadik po vzgoji in rezervo.

Potrebno seme = zaokrožitev navzgor (sadike / (kalivost × uporabne sadike po vzgoji) × (1 + rezerva)). Za 1.000 sadik, 95 % kalivosti, 90 % uporabnih sadik in 5 % rezerve potrebuješ **1.229 semen**.

Izračun primerja potrebo z zalogo iste kulture in sorte, po rokih uporabnosti na datum setve. Seme v gramih pretvori samo z znano maso tisoč semen. Delov semen ne šteje kot uporabno zalogo. Prikaže primanjkljaj in možna pakiranja iz evidence; to niso potrjene ponudbe dobavitelja.

- Predpostavlja eno seme na sadiko in enosemenske pelete. Več semen na sadiko oziroma večsemenski peleti niso podprti.
- Kalivost in uspešnost vzgoje sta ročno vneseni predpostavki za izračun, ne potrdilo kakovosti vsake serije.
- Izračun velja za en načrt; druge setve in rezervacije niso odštete. Pokritosti več izračunov ne seštevaj, ker uporabljajo isto zalogo.
- Vnosi veljajo samo za trenutni pogled. Ob spremembi podatkov se rezultat razveljavi; pri izbiri drugega načrta ponovno vnesi predpostavke.
- Načrta, semenske zaloge in baze ne spreminja. Obstoječa gramovska napoved neposrednih setev ostane ločena.

API: `GET /api/seed-inventory/nursery-forecast/{plan_id}` s parametri `target_plants`, `germination_pct`, `nursery_survival_pct`, `reserve_pct`. Zahteva načrt s statusom planned, današnjo ali prihodnjo setvijo in veljavnim datumom presajanja. Migracija ni potrebna.

Preverjeno: **193 backend testi, 18 frontend testov, produkcijska gradnja in prikaz na ločenih testnih podatkih**. Windows in Android paketa izdeluje obstoječi GitHub postopek.
