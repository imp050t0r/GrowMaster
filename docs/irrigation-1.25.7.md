# GrowMaster 1.25.7 — individualni in skupni ventili

V profilu grede uporabnik izbere individualni ali skupni ventil. Za skupni ventil morajo vse grede v isti fizični skupini izbrati skupni način in isti OpenSprinkler entity ID. Posamezni ventil ostaja vezan na gredico; sprememba aktivne kulture ne spremeni povezave.

Dnevni pregled skupnega ventila pripravi en skupinski osnutek. Priprava je blokirana, če katera priključena gredica nima aktivne zasaditve, svežega izračuna, meritve/Smart Irrigation stanja ali priporočila za zalivanje. Vse gredice morajo isti dan priporočati zalivanje. Skupni čas je največji od potrebnih časov posameznih gredic, vendar ne sme preseči najmanjšega dovoljenega časa, izračunanega iz pretoka, površine, preostalega primanjkljaja, največjega odmerka in omejitve postaje.

Skupinski osnutek se samo prikaže. GrowMaster ga ne pošlje in ne zažene ventila. Vrednosti pretoka morajo predstavljati posamezne veje pri skupnem ventilu; če hidravlična razporeditev tega ne omogoča ali izračuni gredic niso primerljivi, skupnega osnutka ne uporabi.
