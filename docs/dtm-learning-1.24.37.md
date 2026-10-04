# GrowMaster 1.24.37 – potrjeni predlog DTM iz zgodovine

V zavihku Plan, pod primerjavo napovedane in dejanske žetve, je razdelek Predlog popravka DTM. Prikaže predlog za posamezen odprt načrt s prihodnjo setvijo. Gumb POTRDI POPRAVEK ZA TA NAČRT spremeni njegovo dinamično napoved; ODSTRANI POPRAVEK pred začetkom setve obnovi napoved pred potrditvijo.

Za predlog so potrebne zaključene zasaditve iste kmetije, sorte, sezone in začetka štetja dni (setev ali presajanje), z najmanj tremi različnimi referenčnimi datumi. Več gred z istim začetnim datumom šteje kot en termin: najprej izračunamo mediano odmikov za vsak datum, nato mediano med termini. Vir je prva zabeležena žetev in začetna shranjena napoved. Neveljavni, naknadno ustvarjeni, temperaturni/GDD ali prestavljeni referenčni podatki niso vključeni. Uporabljeni zapisi so vidni v pregledu.

Popravek je omejen na 20 % osnovne sezonske napovedi in največ 7 dni. Če se odmiki med termini razlikujejo za več kot večjo vrednost med 4 dnevi in 20 % DTM, predloga ni. To so omejitve začetnega načrtovalnega pristopa, ne znanstveno umerjen model. Majhne razlike, ki se zaokrožijo na nič, ne ustvarijo predloga. Zanesljivost ostane nizka; interval se lahko razširi, ne zoži.

Pred potrditvijo preveri primerljivost pridelave in načina pobiranja. Evidenca še ne ločuje vseh rastnih pogojev in načinov žetve. Prvo pobiranje je odvisno tudi od odločitev pri delu. Manjkajoči podatki ne ustvarjajo popravka za nazaj.

Kataloški DTM, prvotno načrtovani datumi in začetni posnetek napovedi ostanejo ohranjeni. Potrditev velja samo za izbrani načrt. Razlaga shranjuje uporabljene zapise, velikost popravka, čas potrditve in napoved pred potrditvijo. Aktiviranje načrta uporablja obstoječi prenos napovedi. Nov izračun ali premik sukcesije odstrani ta popravek in zahteva novo presojo. Premik na drugo gredo sam ohrani napoved; primerljivost novih razmer presodi uporabnik.

Shema ostaja 0015_bed_release_date. Nova migracija in nove odvisnosti niso potrebne: popravek je shranjen v obstoječi razlagi dinamične napovedi. Varnostna kopija vključuje tudi potrditev in napoved za obnovo.

Preverjeno: 102 backend testov (18 novih), 18 frontend testov, produkcijska gradnja in dejanska potrditev/odstranitev prek vmesnika na ločeni testni bazi. Preverjeni so nespremenjeni načrtovani datumi in začetni posnetek, omejitev popravka, izločanje neprimerljivih zapisov, zavrnitev zastarelega predloga ter obnovitev kopije. Opozorila o zastarelih knjižničnih vmesnikih in velikosti frontend paketa ostajajo.

Namestitev: ob delujočem Docker Desktop zaženi GrowMaster-Setup-1.24.37.exe in ohrani obstoječo mapo podatkov. Po nadgradnji preveri različico 1.24.37 in odpri Plan. Paket je pripravljen, ni samodejno nameščen. Neposredna namestitev iz razvojnega okolja je omejena zaradi dostopa do Dockerja.
