# Samostojna povezava Smart Irrigation

V Več → Plan → Namakanje izberi gredico in razširi »Profil grede — tla, pretok in WH51«.
Vnesi dejanski ID senzorja (za A1: `sensor.smart_irrigation_a1`) in klikni
»SHRANI POVEZAVO SMART IRRIGATION«. Gumb ne zahteva podatkov o tleh ali pretoku.
Uspeh ali napaka se prikaže ob gumbu. Neshranjene vrednosti profila ostanejo v obrazcu.

Povezava sama ne ustvari popolnega profila, ne izvede klica Home Assistanta in ne
omogoči zalivanja. »PREBERI NASTAVLJENE SENZORJE« lahko prebere tudi tako povezani
senzor, vendar njegov rezultat še ni dovoljenje za izvedbo namakanja.

`PUT /api/irrigation/beds/{bed_id}/smart-irrigation` sprejme samo
`smart_irrigation_entity` iz domene `sensor.smart_irrigation_*`.
Pri obstoječem profilu spremeni samo povezavo. Sicer migracija
`0022_irrigation_smart_mappings` omogoči ločeno shranjevanje. Ob kasnejšem
shranjevanju popolnega profila se povezava prenese, če je odjemalec ni podal;
izrecno poslana vrednost (tudi null) ima prednost.
Nove povezave so vključene v varnostno kopijo; stare kopije brez te tabele ostanejo podprte.

Preverjanje povezave HA zdaj prikazuje čakanje, uspeh ali napako neposredno ob
kontrolah. Neuspešen ponovni preizkus odstrani prejšnjo oznako »povezano«.
