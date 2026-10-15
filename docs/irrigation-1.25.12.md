# GrowMaster 1.25.12 — dnevni pregled Smart Irrigation

V razdelku **Več → Namakanje** se dnevni pregled za aktivne gredice samodejno osveži ob odprtju, ob vrnitvi v aplikacijo in vsakih 15 minut.

## Gredice brez WH51

Za profil grede izberi **Brez talnega senzorja — Smart Irrigation** in vnesi entity ID trajanja cone iz Home Assistanta, na primer `sensor.smart_irrigation_greda_1`. Home Assistant mora vrniti številsko stanje v sekundah; GrowMaster preveri, da je izračun star največ šest ur.

GrowMaster v pregledu prikaže priporočilo Smart Irrigation:

- trajanje 0 sekund pomeni, da zalivanje ni priporočeno;
- trajanje nad 0 sekund pomeni, da Smart Irrigation priporoča zalivanje;
- količina vode je ocenjena kot `pretok grede (l/min) × trajanje (s) ÷ 60`.

Za oceno litrov mora biti nastavljen skupni pretok vseh kapljičnih cevi na gredici. Pretok lahko vneseš neposredno ali ga oceniš iz skupne dolžine cevi, razmika med kapljači in pretoka enega kapljača. Ocena velja le toliko, kolikor so pravilni ti podatki in tlak med delovanjem.

Smart Irrigation še naprej vodi svojo vremensko bilanco in izračun trajanja. GrowMaster primerja Kc za aktivno kulturo in fazo z atributom `multiplier` v Smart Irrigation. Če se vrednosti razlikujeta, označi Kc za posodobitev in blokira osnutek ventila za to gredico. GrowMaster pripravi Kc-osnutek za trenutno aktivno kulturo na vsaki gredici, tudi če dnevnega izračuna nisi shranil. Fazo GrowMaster izračuna iz deleža cikla med setvijo in pričakovanim pobiranjem: začetna do 20 %, polna rast od 20 do 80 %, pozna faza od 80 % do pobiranja. Če obstaja dinamična napoved začetka pobiranja, uporabi to. V pregledu pokaže tudi uporabljeni napredek cikla. Po potrditvi lahko GrowMaster pošlje Kc v Smart Irrigation. To ne sproži izračuna ali zalivanja. Po posodobitvi Kc počakaj na naslednji izračun Smart Irrigation; dotlej preveri stanje cone, preden uporabiš priporočilo.

## Gredice z WH51

WH51 način ostaja ločen. Gredico ročno dodeli eni od največ 16 skupin senzorjev; isti senzor lahko predstavlja več gredic. Gredice brez senzorja pustijo skupino WH51 prazno in uporabljajo Smart Irrigation.

## Ventili in skupne cone

Dnevni pregled lahko pripravi OpenSprinkler osnutek. GrowMaster ne pošlje ukaza za zagon ventila in ne označi zalivanja kot izvedenega. Osnutek pred uporabo preveri in zaženi ročno v Home Assistantu.

Pri skupnem ventilu morajo biti vse nanj vezane aktivne gredice nastavljene kot skupinske. Predlog je blokiran, če katera gredica ni pripravljena ali če bi skupni čas presegel varno omejitev ene od njih. Ocena litrov za vsako gredico uporablja njen vpisani pretok.

## Omejitve

- GrowMaster ne meri dejanskega pretoka vode.
- Smart Irrigation mora imeti pravilno konfigurirano vremensko bilanco, urnik, Kc in cono.
- Če senzor trajanja ni svež, nima enote `seconds` ali ga Home Assistant ne doseže, pregled zahteva preverjanje.
- Ročni izračun vodne bilance GrowMasterja z ET₀, dežjem in začetnim primanjkljajem je ločena funkcija.
- Ventili se ne odpirajo samodejno.
