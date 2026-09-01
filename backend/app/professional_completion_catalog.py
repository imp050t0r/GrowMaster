"""Professional source coverage for every remaining GrowMaster crop.

This catalogue is deliberately additive. It gives every crop at least one
traceable commercial cultivar or professional crop profile while preserving
all local, heritage and user-entered varieties.
"""

from app.eu_seed_catalog import eu_variety


VOLTZ_BABY_LEAF = "https://es.es.voltz-maraichage.com/sites/default/files/2024-11/lgdm_es_bio_25_web.pdf"
VOLTZ_VEGETABLES = "https://be.voltz-maraichage.com/sites/default/files/2023-10/LGDM_Bio_2024_Ipad_compressed_0.pdf"
JOHNNYS_ASIAN = "https://www.johnnyseeds.com/vegetables/greens/asian-greens/"
TOZER_LEAF = "https://www.tozerseeds.com/product-category/leaf/?country=EU"


def pro(crop, family, name, days, source_name, source_url, traits, note, **kwargs):
    return eu_variety(
        crop, family, name, days, source_name, source_url, traits, note, **kwargs
    )


PROFESSIONAL_COMPLETION_CATALOG = [
    # Asian vegetables already present in GrowMaster but previously unsourced.
    pro("Choi Sum", "Brassicaceae", "Green 70 D Improved", 42, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Uveljavljen komercialni choi sum za mlada cvetna stebla in liste.",
        "Hladnejša pomladna ali jesenska pridelava; poleti hitro uhaja v cvet.", category="Azijska"),
    pro("Daikon", "Brassicaceae", "Minowase", 60, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Klasičen dolg bel daikon za sveži trg in predelavo.",
        "Za Gorenjsko je najzanesljivejša pozno-poletna setev za jesenski pridelek.", category="Azijska"),
    pro("Edamame", "Fabaceae", "Midori Giant", 85, "Johnny's Selected Seeds", "https://www.johnnyseeds.com/vegetables/beans/soybeans-edamame/",
        "Profesionalni zgodnji edamame z velikimi zelenimi zrni.",
        "Sej v ogreta tla; v hladnejšem letu uporabi najtoplejšo lego.", category="Azijska"),
    pro("Kailan", "Brassicaceae", "Green Lance", 55, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Komercialni kitajski brokoli za stebla, liste in mlade cvetove.",
        "Primeren za spomladanske in jesenske sukcesije.", category="Azijska"),
    pro("Komatsuna", "Brassicaceae", "Green River", 35, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Hitra pokončna komatsuna za baby leaf ali polno velikost.",
        "Zanesljiva hladnosezonska azijska listnata kultura.", category="Azijska", days_baby=24, seed_rate_g_m2=2.5),
    pro("Mibuna", "Brassicaceae", "Green Spray", 40, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Ozkolistna japonska mibuna za šope in mlade liste.",
        "Sej spomladi in od poznega poletja dalje.", category="Azijska", days_baby=24, seed_rate_g_m2=2.5),
    pro("Pekinško zelje", "Brassicaceae", "Bilko F1", 75, "Bejo", "https://www.bejo.com/chinese-cabbage",
        "Profesionalni F1 tip pekinškega zelja za izenačene glave in jesensko spravilo.",
        "Za Gorenjsko je najvarnejša poletna setev za jesenski pridelek.", category="Azijska", seed_forms="profesionalno F1 seme"),
    pro("Shiso", "Lamiaceae", "Britton", 60, "Johnny's Selected Seeds", "https://www.johnnyseeds.com/herbs/shiso/",
        "Komercialni zeleno-rdeči shiso za sveže liste in garnish.",
        "Toploljubna kultura; vzgoji sadike in presadi po slani.", category="Azijska"),
    pro("Shungiku", "Asteraceae", "Oasis", 45, "Johnny's Selected Seeds", JOHNNYS_ASIAN,
        "Profesionalni užitni krizantemin list za azijski sveži trg.",
        "Najboljši je v hladnejšem delu sezone; obiraj mlade vršičke.", category="Azijska"),

    # Baby leaf: professional EU catalogue source and market-purpose profiles.
    pro("Baby leaf batavia", "Asteraceae", "Tourbillon", 30, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Profesionalna zelena batavia za gosto baby-leaf setev.", "EU profesionalni baby-leaf profil za več sukcesij.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.2, seed_forms="profesionalno seme"),
    pro("Baby leaf endivija", "Asteraceae", "Natacha", 30, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Profesionalna endivija za mlade liste z dobro izenačenostjo.", "Primerna za hladnejše sukcesije in jesenski tunel.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.5, seed_forms="profesionalno seme"),
    pro("Baby leaf kitajsko zelje", "Brassicaceae", "Tokyo Bekana", 25, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Svetlozelen kitajski list za hitro baby-leaf pridelavo.", "Sej v hladnejših terminih za nežne liste.",
        category="Baby leaf", days_baby=25, seed_rate_g_m2=2.5, seed_forms="profesionalno seme"),
    pro("Baby leaf komatsuna", "Brassicaceae", "Green River", 24, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Pokončna zelena komatsuna za baby leaf.", "Primerna za več rezov v hladnejših terminih.",
        category="Baby leaf", days_baby=24, seed_rate_g_m2=2.5, seed_forms="profesionalno seme"),
    pro("Baby leaf listna solata", "Asteraceae", "Tango", 30, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Nazobčana zelena listna solata za profesionalni baby leaf.", "Gosta direktna setev in zaporedni rezi.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.2, seed_forms="profesionalno seme"),
    pro("Baby leaf mešanica", "Mešanica", "Professional Mild Leaf Mix", 28, "Tozer Seeds Europe", TOZER_LEAF,
        "Profesionalni koncept ločeno posejanih blagih listov, združenih po pranju.",
        "Komponente sej ločeno in mešaj po masi; tako ohraniš enakomernost in nadzor zaloge.",
        category="Baby leaf", days_baby=28, seed_rate_g_m2=2.0, seed_forms="profesionalno seme"),
    pro("Baby leaf mizuna", "Brassicaceae", "Mizuna F1", 24, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Izenačena zelena mizuna za profesionalni baby leaf.", "Hitra hladnosezonska komponenta azijskih mešanic.",
        category="Baby leaf", days_baby=24, seed_rate_g_m2=2.5, seed_forms="profesionalno seme"),
    pro("Baby leaf ohrovt", "Brassicaceae", "Red Russian", 28, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Rdečežilni ohrovt za mlade liste in barvni kontrast.", "Reži mlade liste pred razvojem grobih pecljev.",
        category="Baby leaf", days_baby=28, seed_rate_g_m2=2.5, seed_forms="profesionalno seme"),
    pro("Baby leaf pak choi", "Brassicaceae", "Green Revolution F1", 25, "Tozer Seeds Europe", TOZER_LEAF,
        "Pokončen zelen pak choi za mlade liste.", "Gosta setev za baby leaf; prednost pomlad in jesen.",
        category="Baby leaf", days_baby=25, seed_rate_g_m2=2.5, seed_forms="profesionalno F1 seme"),
    pro("Baby leaf radič", "Asteraceae", "Zuccherina di Trieste", 28, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Svetlozelen listni radič za hitro rezanje.", "Primeren za zaporedne setve in več rezov.",
        category="Baby leaf", days_baby=28, seed_rate_g_m2=2.0, seed_forms="profesionalno seme"),
    pro("Baby leaf rimska solata", "Asteraceae", "Breen", 30, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Kompaktna bronasto rdeča rimska solata za baby leaf.", "Barvna komponenta profesionalnih mešanic.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.2, seed_forms="profesionalno seme"),
    pro("Baby leaf tatsoi", "Brassicaceae", "Tah Tsai", 25, "Tozer Seeds Europe", TOZER_LEAF,
        "Temnozelen tatsoi za gost baby leaf.", "Zelo primeren za hladne termine in azijske mešanice.",
        category="Baby leaf", days_baby=25, seed_rate_g_m2=2.5, seed_forms="profesionalno seme"),
    pro("Baby leaf špinača", "Amaranthaceae", "Carmel F1", 25, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Profesionalna gladkolistna baby špinača z izenačeno pokončno rastjo.", "Hladnosezonska pridelava; poleti je tveganje uhajanja v cvet.",
        category="Baby leaf", days_baby=25, seed_rate_g_m2=3.5, seed_forms="profesionalno F1 seme"),
    pro("Cikorija", "Asteraceae", "Spadona", 30, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Ozkolistna cikorija za rezanje mladih listov.", "Profesionalni profil za gosto setev in več rezov.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.5),
    pro("Divja rukola", "Brassicaceae", "Dragon's Tongue", 30, "Tozer Seeds Europe", TOZER_LEAF,
        "Profesionalna divja rukola z izrazito obliko in okusom.", "Za več rezov; v vročini spremljaj uhajanje v cvet.",
        category="Baby leaf", days_baby=25, seed_rate_g_m2=1.8),
    pro("Mladi listi rdeče pese", "Amaranthaceae", "Bulls Blood", 28, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Temno rdeči mladi listi pese za barvni baby leaf.", "Gosta direktna setev; reži pred odebelitvijo korena.",
        category="Baby leaf", days_baby=28, seed_rate_g_m2=4.0),
    pro("Salatni trpotec", "Plantaginaceae", "Erba Stella", 35, "Voltz Maraîchage EU", VOLTZ_BABY_LEAF,
        "Ozkolistni salatni trpotec za posebne mešanice.", "Hladnosezonska specialiteta za mlade liste in več rezov.",
        category="Baby leaf", days_baby=30, seed_rate_g_m2=1.5),

    # Standard field and protected crops with no professional source in seed DB.
    pro("Bob", "Fabaceae", "Aquadulce Claudia", 90, "Voltz Maraîchage EU", VOLTZ_VEGETABLES,
        "Profesionalni zgodnji bob z dolgimi stroki.", "Primeren za zgodnjo spomladansko setev v Sloveniji."),
    pro("Feferon", "Solanaceae", "Lombardo", 125, "Voltz Maraîchage EU", VOLTZ_VEGETABLES,
        "Dolg blag feferon za svežo prodajo in vlaganje.", "Vzgoji sadike in presadi po slani; tunel podaljša obiranje."),
    pro("Jajčevec", "Solanaceae", "Bonica F1", 120, "Voltz Maraîchage EU", VOLTZ_VEGETABLES,
        "Izenačen profesionalni F1 jajčevec za sveži trg.", "Za Gorenjsko je priporočljiva pridelava v tunelu.", seed_forms="profesionalno F1 seme"),
    pro("Krompir", "Solanaceae", "Agria", 120, "EUROPLANT", "https://www.europlant.biz/en/list-of-varieties/agria/",
        "Profesionalna srednje pozna sorta za sveži trg, skladiščenje in predelavo.", "Uporabi certificiran semenski krompir."),
    pro("Motovilec", "Caprifoliaceae", "Vit", 55, "Voltz Maraîchage EU", VOLTZ_VEGETABLES,
        "Profesionalni temnozelen motovilec za polje in zaščiten prostor.", "Najprimernejši za jesensko-zimski program."),
    pro("Peteršilj", "Apiaceae", "Gigante d'Italia", 75, "Voltz Maraîchage EU", VOLTZ_VEGETABLES,
        "Profesionalni gladkolistni peteršilj z močnim ponovnim odganjanjem.", "Primeren za sukcesije in več rezov."),
    pro("Repa", "Brassicaceae", "Tokyo Cross F1", 35, "Takii Europe", "https://takii.eu/",
        "Zgodnja izenačena bela F1 repa za šope in mlade korene.", "Primerna za pomladne in jesenske setve.", seed_forms="profesionalno F1 seme"),
    pro("Čebula", "Amaryllidaceae", "Hylander F1", 125, "Bejo", "https://www.bejo.com/onion",
        "Profesionalna skladiščna čebula z izenačenimi čebulami.", "Za neposredno setev ali vzgojo sadik; preveri lokalno dobavljivost.", seed_forms="profesionalno F1 seme"),
    pro("Česen", "Amaryllidaceae", "Messidrome", 220, "Germidour", "https://www.germidour.com/en/our-varieties/",
        "Profesionalni jesenski beli česen za certificiran sadilni material.", "Sadi zdrav certificiran material; ne obravnavaj ga kot seme v botaničnem smislu.", seed_forms="certificiran sadilni česen"),

    # Remaining Indian crops without a professional source.
    pro("Guar", "Fabaceae", "Punjab Vegetable Guar-1", 51, "Punjab Agricultural University",
        "https://pau.edu/cohf/index.php?DO=viewMatter&_act=manageDepartments&intDepTitleID=337&intLinkID=5",
        "Zgodnji profesionalni vegetable guar s 5–6 nežnimi stroki v grozdu; uradno prvo obiranje 51 dni po setvi.",
        "Toploljubna kultura; za Gorenjsko uporabi najtoplejšo lego ali tunel.", category="Indijska"),
    pro("Malabarska špinača", "Basellaceae", "Green Stem", 55, "Johnny's Selected Seeds",
        "https://www.johnnyseeds.com/vegetables/greens/malabar-spinach/",
        "Toploljubna plezajoča listnata kultura za večkratno obiranje.",
        "Vzgoji sadike, zagotovi oporo in presadi po slani; tunel močno podaljša pridelek.", category="Indijska"),
]
