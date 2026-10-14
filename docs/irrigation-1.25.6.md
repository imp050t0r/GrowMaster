# GrowMaster 1.25.6 — dnevni pregled akcij po gredici

Vsaka gredica ima trajno povezavo do svoje OpenSprinkler postaje/ventila. Aktivna zasaditev določa trenutno kulturo in njen profil; menjava kulture ne spremeni povezave gredice z ventilom.

Dnevni pregled za način brez WH51 bere izračunano trajanje Smart Irrigation cone v sekundah. Za način z WH51 uporablja shranjeni dnevni odmerek, svež senzor vlage in pretok grede za izračun trajanja. V obeh primerih pripravi prikaz akcije `opensprinkler.run_station` samo, če so preverjanja uspešna, je ventil enolično povezan z eno gredico in trajanje ne presega omejitve ventila. Pri načinu z WH51 je potreben shranjen današnji izračun s statusom `irrigate`.

Dnevni pregled akcijo samo prikaže; ne pošlje je v Home Assistant in ne odpre ventila. Zagon ostaja ročen v Home Assistantu. Za samodejno delovanje je še treba dodati eksplicitno uporabniško omogočitev, urnik, evidenco poskusov in izvedb, preprečevanje podvojitev, varno obnovitev po prekinitvi ter preverjanje odziva OpenSprinklerja.
