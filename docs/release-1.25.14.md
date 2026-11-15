# GrowMaster 1.25.14

- Povezavo Smart Irrigation za gredico je mogoče shraniti brez podatkov o tleh z gumbom SHRANI POVEZAVO SMART IRRIGATION.
- Povezave so vključene v varnostne kopije; nadgradnja doda tabelo za predhodne povezave senzorjev.
- Preverjanje povezave Home Assistanta prikaže rezultat neposredno ob gumbu.
- S01 ostaja na voljo za gredico; skupna črpalka je predvidena na ločenem releju.
- Shranjevanje povezave ne zažene zalivanja in ne nadomesti popolnega profila grede.

Preverjanje popravka: 557 backend testov (556 v polnem zagonu in preostali test po uskladitvi pričakovane sheme), 7 frontend testov ter uspešna frontend gradnja. Namestitvene pakete dodatno preveri GitHub Actions.

Nadgradnja: pred namestitvijo ustvari varnostno kopijo v GrowMasterju. Namesti GrowMaster-Setup-1.25.14.exe. Po zagonu preveri oznako 1.25.14.
Za A1: Več → Plan → Namakanje → Gredica A1 → Profil grede → sensor.smart_irrigation_a1 → SHRANI POVEZAVO SMART IRRIGATION.
Samodejno zalivanje ostane izklopljeno do preveritve celotne namestitve.
