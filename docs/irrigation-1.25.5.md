# GrowMaster 1.25.5 — nastavitev Home Assistanta v aplikaciji

Povezavo s Home Assistantom nastavi uporabnik v razdelku Namakanje: vnese URL in dolgoročni dostopni žeton, shrani povezavo ter uporabi gumb za preverjanje. Prazno polje za žeton ob urejanju ohrani že shranjeni žeton; vnos nove vrednosti ga zamenja. Povezavo je mogoče izbrisati.

Backend shrani URL in šifrirani žeton v datoteko v trajnem `/data/secrets` imeniku GrowMasterja. Ključ za šifriranje je v ločeni datoteki z omejenimi dovoljenji. Žeton ni trajno shranjen v brskalniku, bazi, dnevniku ali izvozni varnostni kopiji. Namestitev mora ohraniti GrowMasterjev podatkovni volumen; po izgubi volumna je treba povezavo nastaviti znova. Uporabi lokalni URL, ki je dosegljiv iz backend Docker vsebnika, na primer `http://192.168.1.50:8123`; ne uporabljaj Tailscale imena, če GrowMaster gostitelj ni v Tailscale omrežju.

V obstoječem `.env` nastavitev ostane podprta kot nadomestna možnost. Ko uporabnik shrani povezavo v aplikaciji, ima ta prednost pred spremenljivkami okolja. API status vrne le URL in podatek, ali je žeton nastavljen; žetona nikoli ne vrne. Nastavitveni endpoint je zaščiten z GrowMaster prijavo.

Povezava Home Assistanta omogoča preverjanje API-ja, branje izrecno nastavljenih senzorjev in omejeno pošiljanje Kc v Smart Irrigation po obstoječem pregledu. Ta nastavitev sama ne omogoči samodejnega odpiranja ventilov.
