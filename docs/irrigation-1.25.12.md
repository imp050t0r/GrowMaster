# GrowMaster 1.25.12 — dnevni pregled Smart Irrigation

V razdelku **Plan → Namakanje** se dnevni pregled za aktivne gredice samodejno osveži ob odprtju, ob vrnitvi v aplikacijo in vsakih 15 minut.

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

Dnevni pregled lahko pripravi OpenSprinkler osnutek za ročni zagon. Če je samodejno zalivanje izrecno vključeno, lahko GrowMaster ob izbrani uri pošlje zagon samo za sveže in pripravljene Smart Irrigation ventile. Ukaz, ki ga HA sprejme, ni dokaz dejanskega pretoka vode.

Pri skupnem ventilu morajo biti vse nanj vezane aktivne gredice nastavljene kot skupinske. Predlog je blokiran, če katera gredica ni pripravljena ali če bi skupni čas presegel varno omejitev ene od njih. Ocena litrov za vsako gredico uporablja njen vpisani pretok.

## Omejitve

- GrowMaster ne meri dejanskega pretoka vode.
- Smart Irrigation mora imeti pravilno konfigurirano vremensko bilanco, urnik, Kc in cono.
- Če senzor trajanja ni svež, nima enote `seconds` ali ga Home Assistant ne doseže, pregled zahteva preverjanje.
- Ročni izračun vodne bilance GrowMasterja z ET₀, dežjem in začetnim primanjkljajem je ločena funkcija.
- Samodejno zalivanje je privzeto izključeno; ventile lahko GrowMaster odpre samo, če uporabnik avtomatiko izrecno vklopi in so vsi pogoji pripravljeni.


## Samodejno zalivanje

Avtomatika je privzeto izključena. V razdelku **Plan → Namakanje** jo je mogoče izrecno vključiti in določiti lokalno uro prvega dnevnega preverjanja. GrowMaster nato vsakih pet minut preveri današnji sveži Smart Irrigation izračun. Če se je Kc spremenil zaradi nove kulture ali rastne faze, GrowMaster najprej pošlje posodobitev Kc in počaka na nov izračun cone.

Ventil se sproži le, ko je gredica pripravljena, Smart Irrigation priporoča zalivanje, Kc ustreza aktivni kulturi in fazi ter so ventil in omejitve trajanja pravilno nastavljeni. Za skupni ventil morajo biti pripravljene vse gredice v skupini. Po vsakem ukazu GrowMaster shrani stanje za ta ventil in dan; negotovega odziva Home Assistanta ne ponovi samodejno. Stanje **oddano** pomeni, da je Home Assistant sprejel ukaz, ne pa potrditve fizičnega pretoka vode. GrowMaster ne meri pretoka.

Ob vklopu avtomatike GrowMaster zabeleži čas vklopa in čaka na Smart Irrigation izračun z novejšim časom. Če je bil zadnji izračun narejen pred vklopom ali pred samodejno spremembo Kc, ventil ostane zaprt do naslednjega izračuna.
