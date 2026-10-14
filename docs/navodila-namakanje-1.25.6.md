# Navodila za namakanje v GrowMasterju 1.25.5

Ta navodila pokrivajo obe možnosti profila grede. Uporabiš ju lahko tudi skupaj: nekatere grede imajo WH51, druge ostanejo brez talnega senzorja.

## Pred začetkom: Home Assistant

1. V GrowMasterju odpri **Več → Namakanje**.
2. V razdelku **Smart Irrigation prek Home Assistanta** vnesi URL, dosegljiv iz GrowMaster strežnika, npr. `http://192.168.1.50:8123`, in dolgoročni dostopni žeton.
3. Klikni **SHRANI POVEZAVO**, nato **PREVERI POVEZAVO**. Uspeh je prikazan kot **povezano**.
4. Gumb **PREBERI NASTAVLJENE SENZORJE** prikaže samo entitete, ki so že vpisane v konfiguracijo skupin WH51 oziroma v strežniški seznam vremenskih entitet. Ne išče samodejno vseh naprav.

Če GrowMaster teče v Dockerju, mora biti URL dosegljiv iz backend vsebnika. Če `homeassistant.local` ne deluje, uporabi lokalni IP Home Assistanta. Žetona ne deli in ga ne pošiljaj v posnetkih zaslona.

## Skupni koraki za gredico in kulturo

1. V **Gredice** ustvari gredice in jim zabeleži pravilne površine. V **Setve** naj bo za vsako trenutno aktivno zasaditev vpisana prava kultura in datum.
2. Odpri **Namakanje**, izberi aktivno kulturo in gredico.
3. Odpri **Profil kulture — koeficienti in korenine**. Vnesi Kc za začetno, polno in pozno fazo, učinkovito globino korenin, dovoljeni delež izsušitve ter vir podatkov. Uporabi vrednosti, primerne za dejansko kulturo, tla in način pridelave; če jih nimaš, jih najprej preveri pri strokovnem viru.
4. Shrani profil kulture.
5. Odpri **Profil grede — tla, pretok in WH51**. Izberi namakalni način po enem od spodnjih postopkov.
6. Shrani profil grede. Vsako gredico nastavi posebej. Trenutna različica ne sešteva hidravličnih zahtev več gredic na skupnem ventilu.

## Možnost A: gredica z WH51

Uporabi, ko je senzor fizično nameščen na tej lokaciji oziroma predstavlja skupino podobnih gredic.

### 1. Nastavi skupino WH51

1. V razdelku **WH51 skupine (največ 16)** izberi številko skupine.
2. Vpiši razumljivo ime, npr. `WH51 severne grede`.
3. V Home Assistantu poišči entiteto senzorja vlage, npr. `sensor.xxx_soil_moisture`, in njen entity ID vpiši v skupino.
4. Klikni **SHRANI SKUPINO**. Vsaka skupina ima en entity ID.

### 2. Dodeli grede senzorju

1. V profilu posamezne grede izberi **S senzorjem vlage v tleh**.
2. V polju **Ročno dodeljena WH51 skupina** izberi ustrezno skupino.
3. Več gredic lahko ročno dodeliš isti skupini. Dodelitve ostanejo, dokler jih sam ne spremeniš.
4. Vnesi poljsko kapaciteto in točko venenja kot **volumenski delež vode v tleh (%)**, učinkovitost namakanja, največji odmerek, suhi/mokri prag senzorja in vir umerjanja. Ne vnašaj WH51 odstotka v polje poljske kapacitete.
5. Izberi namakalno cono ter vpiši HA entity ID Smart Irrigation cone, kjer je potrebno za urnik. Shrani profil.

### 3. Dnevni pregled

1. V **Dnevnem izračunu** izberi datum in fazo rasti. Kultura se predizbere iz aktivne setve; preveri, da je pravilna.
2. Vnesi začetni primanjkljaj, ET₀, učinkoviti dež, že izvedeno zalivanje in vir podatkov.
3. Za način s senzorjem GrowMaster prebere meritev iz dodeljene WH51 skupine. Meritev mora biti številčna in največ šest ur stara.
4. Klikni **IZRAČUNAJ NAMAKANJE** za predogled ali **IZRAČUNAJ IN SHRANI DAN** za shranitev.
5. Preglej status, opozorila in predlagani odmerek. Ročno potrdi, da ustreza dejanskim razmeram. GrowMaster še ne odpre ventila.

## Možnost B: brez WH51, z vremensko bilanco Smart Irrigation

Uporabi za gredico brez talnega senzorja. V tem načinu WH51 skupine ne dodeliš.

### 1. Nastavi profil grede

1. Izberi **Brez talnega senzorja — Smart Irrigation**.
2. Pusti **Ročno dodeljena WH51 skupina** na **Brez WH51**.
3. V polje **Smart Irrigation cona v Home Assistantu** vnesi entity ID trajanja prave cone, npr. `sensor.smart_irrigation_greda_1`.
4. Nastavi tla, učinkovitost, pretok in največji odmerek, kjer so podatki znani. Izberi namakalno cono in shrani profil.

### 2. Dnevno vnesi in potrdi bilanco

1. Izberi aktivno kulturo in gredico ter ustrezno fazo rasti.
2. Vnesi začetni primanjkljaj, ET₀, učinkoviti dež, že izvedeno zalivanje in vir podatkov. Trenutno GrowMaster teh vrednosti še ne pobira in ne pretvarja samodejno iz vremenske postaje.
3. Klikni **IZRAČUNAJ IN SHRANI DAN** in preglej rezultat. Za naslednji dan preveri preneseni začetni primanjkljaj ter popravi dejanski dež in izvedeno namakanje.
4. Smart Irrigation v Home Assistantu še naprej vodi svojo vremensko bilanco in urnik. GrowMaster lahko iz shranjenega dnevnega izračuna pripravi Kc za cono.

### 3. Pošiljanje Kc v Smart Irrigation

1. Klikni **PRIPRAVI Kc ZA SMART IRRIGATION**.
2. Preglej vsako pripravljeno vrstico, kulturo, fazo, Kc in entity ID cone. Če se karkoli ne ujema, ne pošiljaj; popravi profile oziroma izračun in pripravi osnutek znova.
3. Ko si pregledal osnutke, klikni **POŠLJI Kc V HOME ASSISTANT**.
4. Aplikacija potrdi število poslanih posodobitev Kc. Smart Irrigation še naprej izvaja svoje preračune in urnik.

GrowMaster v tej različici pošilja samo Kc. Ne sproži Smart Irrigation izračuna, urnika ali OpenSprinkler ventila. Pošiljanje Kc samo po sebi ne potrjuje, da se je čas zalivanja spremenil; preveri stanje cone in urnik v Home Assistantu.

## Gredice brez senzorja in gredice s senzorjem skupaj

Za vsako gredico posebej izberi način. Do 16 skupin WH51 lahko ročno razporediš med poljubno število gredic; gredice brez senzorja pustijo skupino na **Brez WH51**. Ne dodeljuj senzorja gredici samo zato, da bi izpolnil nastavitev.

## OpenSprinkler: priprava ročnega osnutka

Ko ima gredica v profilu pravilen OpenSprinkler entity ID postaje, lahko GrowMaster iz današnjega shranjenega izračuna pripravi osnutek akcije. Klikni **PRIPRAVI AKCIJE OPENSPRINKLER**, preveri gredico, postajo, trajanje in opozorila. Osnutek ni samodejno izveden; če ga uporabiš v Home Assistantu, bo tamkajšnja ročna izvedba dejansko zagnala postajo. Pred tem preveri tlak, pretok, ventil in varno največje trajanje.

## Kaj preveriti, če priprava ni dovoljena

- Ali je zasaditev gredice aktivna in kultura pravilna?
- Ali sta profil kulture in profil grede shranjena?
- Ali je izbran pravi način namakanja?
- Za WH51: ali so skupini vpisani pravilen entity ID, številčna vrednost, svež čas meritve in ustrezni pragovi?
- Za Smart Irrigation: ali se entity ID ujema z dejansko cono in ali je senzor trajanja v sekundah?
- Ali je dnevni izračun za današnji dan, shranjen in mlajši od šestih ur?
- Ali se kultura in profili od shranjenega izračuna niso spremenili? Po spremembi ponovno izračunaj in shrani dan.
- Ali je OpenSprinkler postaja pravilno povezana z eno gredico in je trajanje znotraj nastavljene omejitve?

**Varnostno pravilo:** GrowMaster 1.25.5 ne izvaja samodejnega dnevnega odločanja in ne odpira ventilov sam. Vrednosti, vremenske podatke, profile ter vsak osnutek pred uporabo preveri uporabnik.
