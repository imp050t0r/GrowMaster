# Računi in dobropisi

GrowMaster izdani račun shrani kot nespremenljiv posnetek prodajalca, kupca, postavk, cen, datumov in zneska. Poznejše spremembe kupca, naročila ali nastavitev zato ne spremenijo že izdanega dokumenta.

## Tok izdaje

1. Poslovni kupec mora imeti naziv, naslov in davčno številko.
2. Prodajalec mora v nastavitvah prodaje in profilu računa vpisati zahtevane identifikacijske podatke.
3. Račun se izda iz dostavljenega naročila ali poslovne hitre prodaje.
4. Številka se dodeli iz ločenega letnega zaporedja v obliki `R-{prostor}-{naprava}-{leto}-{zaporedje}`.
5. Pri nakazilu je arhivski PDF na voljo takoj.
6. Pri gotovini ali kartici račun čaka na EOR. Končni PDF je zaklenjen, dokler uporabnik ne vnese EOR, ki ga je vrnil zunanji postopek davčnega potrjevanja.
7. Izdani račun se ne briše in ne spreminja. Celotni popravek se izvede z dobropisom `DB-{prostor}-{naprava}-{leto}-{zaporedje}`, ki ostane povezan s prvotnim računom.

## Pomembna omejitev

GrowMaster trenutno nima neposredne povezave s FURS in ne uporablja namenskega digitalnega potrdila. Aplikacija zato sama ne pošilja računa v davčno potrjevanje in ne ustvarja EOR ali ZOI. Vneseni EOR/ZOI mora izvirati iz dejanskega zunanjega postopka. Izdaja dobropisa prav tako ne pomeni, da je bilo kupcu že izvedeno vračilo denarja; denarni tok prikazuje samo dejansko evidentirana plačila in stroške.

Klavzula o DDV je nastavljiva, ker je pravilno besedilo odvisno od davčnega položaja prodajalca. Pred produkcijsko uporabo naj podatke, klavzulo, način številčenja in interni akt pregleda računovodja ali davčni svetovalec.

## Preverjeni uradni viri

- [GOV.SI – davčni postopek in davčno potrjevanje računov](https://www.gov.si/teme/davcni-postopek-in-davcno-potrjevanje-racunov/)
- [PISRS – Zakon o davku na dodano vrednost (ZDDV-1)](https://pisrs.si/pregledNpb?idPredpisa=ZAKO4701&idPredpisaChng=ZAKO6148)
- [FURS – Davčne blagajne, vprašanja in odgovori](https://www.fu.gov.si/fileadmin/Internet/Nadzor/Podrocja/Davcne_blagajne_in_VKR/150717_Davcne_blagajne_-_Vprasanja_in_odgovori.pdf)
