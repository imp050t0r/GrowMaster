# GrowMaster 1.24.38 – Workload Forecast

V zavihku Plan pod koledarjem dela je Tedenska napoved dela. Za isto izbrano obdobje zbere načrtovane setve, presajanja, prve žetve, odprta opravila in potrjene dostave. Po tednih prikaže število aktivnosti, razčlenitev in največ aktivnosti v enem tednu. Načrti in opravila ostanejo nespremenjeni.

Delna ocena ur uporablja dejanski čas zaključenih opravil iste vrste ter enakih mer grede. Potrebni so vsaj trije različni dnevi zaključka. Mediana po posameznih dnevih zagotovi, da več gred obdelanih istega dne ne prevlada kot več neodvisnih terminov. Zgodovina brez zaključnega datuma, s prihodnjim zaključkom ali neveljavnim časom je izključena. Čas aktivnosti brez primerljive zgodovine ni izmišljen in ni vključen v seštevek ur. Ocene so pomoč pri načrtovanju, niso statistično umerjene; razmere in zahtevnost iste vrste dela se lahko razlikujejo.

Razpoložljive ure na teden lahko vneseš za trenutno primerjavo. Če ocenjeni del dela že preseže razpoložljivost, se pokaže opozorilo. Kadar del aktivnosti nima časovne ocene, pregled ne potrjuje, da bo časa dovolj za celotno delo. En koledarski zapis pomeni aktivnost, ne enake količine dela. Delni prvi in zadnji teden prikazujeta samo datume znotraj izbranega obdobja.

Ponovljena pobiranja in opravila, ki še niso ustvarjena, niso vključena. Prve žetve uporabljajo obstoječe načrtovane datume. Podrobnejša napoved spravila je predvidena v 1.24.40. Pregled vzgoje sadik ni del te izdaje.

Shema ostaja 0015_bed_release_date; novih polj, migracije in odvisnosti ni. Pregled ponovno uporabi obstoječi koledar in dejanske čase opravil. Varnostne kopije in postopki shranjevanja ostajajo združljivi.

Preverjeno: 110 backend testov (8 novih), 18 frontend testov, produkcijska gradnja in pregled na ločeni razvojni bazi v brskalniku. Preverjene so meje tednov, delni tedni, minimalna zgodovina, neznani časi, izolacija kmetije, izločanje preklicanih načrtov in opozorilo o preseženi razpoložljivosti. Obstoječa opozorila o zastarelih knjižničnih vmesnikih in velikosti frontend paketa ostajajo.

Namestitev: ob delujočem Docker Desktop zaženi GrowMaster-Setup-1.24.38.exe in ohrani obstoječo mapo podatkov. Nato odpri Plan, v Koledarju dela izberi obdobje in poglej Tedensko napoved dela pod koledarjem. Paket ni samodejno nameščen; dostop razvojnega okolja do Dockerja je omejen.
