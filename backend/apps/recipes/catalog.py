"""Il catalogo iniziale degli ingredienti (progettazione, sezione 3).

Serve a tre cose: suggerire gli ingredienti mentre si scrive una ricetta,
sommare la spesa per reparto e unita' (fase 5) e sapere quali allergeni UE
contiene una ricetta, senza chiederlo all'LLM (ADR 0002 e 0004).

Ogni voce: nome italiano, nome inglese, reparto, allergeni, unita' di
default, grammi per pezzo (se si conta a pezzi), giorni da fresco (vuoto per
la dispensa), se e' un basilare che in casa di solito c'e' gia', sinonimi.
Il catalogo si carica con la migrazione ``0002_catalog`` e si aggiorna con
``manage.py load_catalog`` (non tocca gli ingredienti aggiunti dagli utenti).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Reparti, in ordine di giro al supermercato.
PRODUCE = "produce"
MEAT = "meat"
FISH = "fish"
DAIRY = "dairy"
BAKERY = "bakery"
PANTRY = "pantry"
SPICES = "spices"
FROZEN = "frozen"
DRINKS = "drinks"


@dataclass(frozen=True)
class Item:
    name: str
    name_en: str
    category: str
    allergens: tuple[str, ...] = ()
    unit: str = "g"
    grams_per_piece: int | None = None
    perishable_days: int | None = None
    staple: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


def veg(name, en, days=5, piece=None, aliases=(), unit=None, allergens=()):
    return Item(
        name,
        en,
        PRODUCE,
        tuple(allergens),
        unit or ("pz" if piece else "g"),
        piece,
        days,
        False,
        tuple(aliases),
    )


def fruit(name, en, days=7, piece=None, aliases=(), allergens=()):
    return Item(
        name,
        en,
        PRODUCE,
        tuple(allergens),
        "pz" if piece else "g",
        piece,
        days,
        False,
        tuple(aliases),
    )


def herb(name, en, days=4, aliases=()):
    return Item(name, en, PRODUCE, (), "g", None, days, False, tuple(aliases))


def meat(name, en, days=2, aliases=(), allergens=(), piece=None):
    return Item(
        name, en, MEAT, tuple(allergens), "pz" if piece else "g", piece, days, False, tuple(aliases)
    )


def fish(name, en, days=1, allergens=("fish",), aliases=()):
    return Item(name, en, FISH, tuple(allergens), "g", None, days, False, tuple(aliases))


def dairy(name, en, days=7, unit="g", piece=None, allergens=("milk",), aliases=(), staple=False):
    return Item(name, en, DAIRY, tuple(allergens), unit, piece, days, staple, tuple(aliases))


def pantry(
    name,
    en,
    allergens=(),
    unit="g",
    aliases=(),
    staple=False,
    category=PANTRY,
    piece=None,
    days=None,
):
    return Item(name, en, category, tuple(allergens), unit, piece, days, staple, tuple(aliases))


def spice(name, en, unit="g", staple=True, aliases=(), allergens=()):
    return Item(name, en, SPICES, tuple(allergens), unit, None, None, staple, tuple(aliases))


CATALOG: list[Item] = [
    # --- verdura ---
    veg("cipolla", "onion", 30, 150, ("cipolle", "cipolla bianca", "cipolla dorata")),
    veg("cipolla rossa", "red onion", 30, 150, ("cipolle rosse", "cipolla di tropea")),
    veg("scalogno", "shallot", 30, 30, ("scalogni",)),
    veg("aglio", "garlic", 60, unit="clove", aliases=("spicchio d'aglio", "spicchi d'aglio")),
    veg("porro", "leek", 7, 200, ("porri",)),
    veg("carota", "carrot", 14, 80, ("carote",)),
    veg("sedano", "celery", 10, 40, ("coste di sedano", "gambo di sedano"), allergens=("celery",)),
    veg("patata", "potato", 30, 200, ("patate",)),
    veg("patata dolce", "sweet potato", 21, 250, ("patate dolci", "patata americana")),
    veg("pomodoro", "tomato", 6, 120, ("pomodori",)),
    veg("pomodorini", "cherry tomatoes", 6, aliases=("pomodori ciliegino", "datterini")),
    veg("zucchina", "courgette", 6, 200, ("zucchine", "zucchino", "zucchini")),
    veg("melanzana", "aubergine", 6, 300, ("melanzane",)),
    veg("peperone", "bell pepper", 7, 200, ("peperoni", "peperone rosso", "peperone giallo")),
    veg("zucca", "pumpkin", 30, aliases=("zucca delica", "zucca mantovana", "butternut")),
    veg("broccoli", "broccoli", 5, aliases=("broccolo",)),
    veg("cavolfiore", "cauliflower", 7, 800),
    veg("cavolo verza", "savoy cabbage", 10, aliases=("verza",)),
    veg("cavolo nero", "kale", 5, aliases=("cavolo riccio",)),
    veg("cavolo cappuccio", "cabbage", 14, aliases=("cavolo",)),
    veg("cavolini di bruxelles", "brussels sprouts", 7),
    veg("spinaci", "spinach", 3, aliases=("spinaci freschi", "spinacini")),
    veg("bietole", "chard", 3, aliases=("bieta", "coste")),
    veg("lattuga", "lettuce", 5, 300, ("insalata", "lattuga romana", "iceberg")),
    veg("rucola", "rocket", 3, aliases=("rughetta",)),
    veg("radicchio", "radicchio", 7, 300, ("radicchio rosso",)),
    veg("valeriana", "lamb's lettuce", 3, aliases=("songino",)),
    veg("cetriolo", "cucumber", 7, 250, ("cetrioli",)),
    veg("finocchio", "fennel", 7, 300, ("finocchi",)),
    veg("carciofo", "artichoke", 5, 200, ("carciofi",)),
    veg("asparagi", "asparagus", 3, aliases=("asparago",)),
    veg("fagiolini", "green beans", 4, aliases=("cornetti",)),
    veg("piselli freschi", "fresh peas", 3),
    veg("fave fresche", "broad beans", 3),
    veg("funghi champignon", "button mushrooms", 4, aliases=("champignon", "funghi")),
    veg("funghi porcini", "porcini mushrooms", 3, aliases=("porcini",)),
    veg("mais dolce", "sweet corn", 3, aliases=("mais", "pannocchia")),
    veg("rapa rossa", "beetroot", 10, 150, ("barbabietola", "barbabietole")),
    veg("ravanelli", "radishes", 7),
    veg("cime di rapa", "turnip tops", 3, aliases=("friarielli",)),
    veg("avocado", "avocado", 5, 200),
    veg("zenzero", "ginger", 21, aliases=("zenzero fresco",)),
    veg("peperoncino fresco", "fresh chilli", 7, 10),
    # --- erbe ---
    herb("basilico", "basil", 4),
    herb("prezzemolo", "parsley", 5),
    herb("rosmarino", "rosemary", 10),
    herb("salvia", "sage", 7),
    herb("timo", "thyme", 7),
    herb("menta", "mint", 4),
    herb("erba cipollina", "chives", 4),
    herb("coriandolo", "coriander", 4, ("cilantro",)),
    herb("aneto", "dill", 4),
    # --- frutta ---
    fruit("mela", "apple", 21, 180, ("mele",)),
    fruit("pera", "pear", 7, 180, ("pere",)),
    fruit("banana", "banana", 5, 120, ("banane",)),
    fruit("arancia", "orange", 14, 200, ("arance",)),
    fruit("limone", "lemon", 21, 100, ("limoni", "succo di limone", "scorza di limone")),
    fruit("lime", "lime", 14, 60),
    fruit("mandarino", "mandarin", 10, 80, ("mandarini", "clementine")),
    fruit("pompelmo", "grapefruit", 14, 300),
    fruit("fragole", "strawberries", 3, aliases=("fragola",)),
    fruit("frutti di bosco", "mixed berries", 3, aliases=("mirtilli", "lamponi", "more")),
    fruit("uva", "grapes", 5),
    fruit("kiwi", "kiwi", 10, 80),
    fruit("pesca", "peach", 4, 150, ("pesche", "nettarina")),
    fruit("albicocca", "apricot", 4, 40, ("albicocche",)),
    fruit("ciliegie", "cherries", 4),
    fruit("prugna", "plum", 5, 50, ("prugne", "susine")),
    fruit("melone", "melon", 5, 1200),
    fruit("anguria", "watermelon", 5, aliases=("cocomero",)),
    fruit("ananas", "pineapple", 5, 1000),
    fruit("mango", "mango", 5, 300),
    fruit("fichi", "figs", 3, aliases=("fico",)),
    fruit("melagrana", "pomegranate", 14, 300),
    fruit("cachi", "persimmon", 5, 200),
    fruit("cocco", "coconut", 14),
    # --- carne e salumi ---
    meat("petto di pollo", "chicken breast", 2, ("pollo", "fesa di pollo", "pollo a fette")),
    meat("cosce di pollo", "chicken thighs", 2, ("sovracosce di pollo", "fusi di pollo")),
    meat("tacchino", "turkey", 2, ("fesa di tacchino", "petto di tacchino")),
    meat("macinato di manzo", "minced beef", 1, ("carne macinata", "macinato", "trita")),
    meat("macinato misto", "mixed mince", 1, ("macinato di maiale e manzo",)),
    meat("manzo", "beef", 3, ("bistecca", "fettine di manzo", "spezzatino di manzo", "girello")),
    meat("vitello", "veal", 3, ("fettine di vitello", "scaloppine")),
    meat("maiale", "pork", 3, ("lonza", "braciola di maiale", "filetto di maiale", "costine")),
    meat("salsiccia", "sausage", 3, ("salsicce",)),
    meat("agnello", "lamb", 3, ("costolette di agnello",)),
    meat("coniglio", "rabbit", 2),
    meat("pancetta", "pancetta", 14, ("pancetta affumicata", "pancetta a cubetti", "bacon")),
    meat("guanciale", "guanciale", 21),
    meat("prosciutto crudo", "cured ham", 7, ("crudo", "prosciutto di parma")),
    meat("prosciutto cotto", "cooked ham", 5, ("cotto",)),
    meat("speck", "speck", 14),
    meat("bresaola", "bresaola", 7),
    meat("salame", "salami", 21),
    meat("mortadella", "mortadella", 7),
    meat("wurstel", "frankfurters", 14, ("würstel",)),
    # --- pesce ---
    fish("salmone", "salmon", 2, aliases=("filetto di salmone", "trancio di salmone")),
    fish("salmone affumicato", "smoked salmon", 7),
    fish("merluzzo", "cod", aliases=("filetti di merluzzo", "baccalà", "nasello")),
    fish("orata", "sea bream", aliases=("orate",)),
    fish("branzino", "sea bass", aliases=("spigola",)),
    fish("tonno fresco", "fresh tuna", aliases=("trancio di tonno",)),
    fish("pesce spada", "swordfish"),
    fish("alici", "anchovies", aliases=("acciughe fresche",)),
    fish("sgombro", "mackerel"),
    fish(
        "gamberi", "prawns", 1, ("crustaceans",), ("gamberetti", "mazzancolle", "code di gambero")
    ),
    fish("cozze", "mussels", 1, ("molluscs",)),
    fish("vongole", "clams", 1, ("molluscs",)),
    fish("calamari", "squid", 1, ("molluscs",), ("calamaro", "anelli di calamaro")),
    fish("seppie", "cuttlefish", 1, ("molluscs",), ("seppia",)),
    fish("polpo", "octopus", 1, ("molluscs",)),
    # --- latticini e uova ---
    dairy(
        "uova", "eggs", 21, "pz", 60, ("eggs",), ("uovo", "tuorlo", "tuorli", "albume", "albumi")
    ),
    dairy("latte", "milk", 5, "ml", aliases=("latte intero", "latte parzialmente scremato")),
    dairy("burro", "butter", 30, aliases=("burro chiarificato",)),
    dairy("panna da cucina", "cooking cream", 14, "ml", aliases=("panna",)),
    dairy("panna fresca", "fresh cream", 5, "ml", aliases=("panna da montare",)),
    dairy("yogurt bianco", "plain yogurt", 10, aliases=("yogurt",)),
    dairy("yogurt greco", "greek yogurt", 10),
    dairy("mozzarella", "mozzarella", 4, aliases=("fior di latte",)),
    dairy("mozzarella di bufala", "buffalo mozzarella", 3, aliases=("bufala",)),
    dairy("burrata", "burrata", 3),
    dairy("ricotta", "ricotta", 4),
    dairy("mascarpone", "mascarpone", 7),
    dairy("stracchino", "stracchino", 5, aliases=("crescenza",)),
    dairy("parmigiano reggiano", "parmesan", 60, aliases=("parmigiano", "grana", "grana padano")),
    dairy("pecorino", "pecorino", 60, aliases=("pecorino romano",)),
    dairy("gorgonzola", "gorgonzola", 10),
    dairy("scamorza", "scamorza", 14, aliases=("provola",)),
    dairy("fontina", "fontina", 21),
    dairy("feta", "feta", 14),
    dairy("formaggio spalmabile", "cream cheese", 10, aliases=("philadelphia",)),
    # --- pane e forno ---
    pantry(
        "pane",
        "bread",
        ("gluten",),
        aliases=("pane casereccio", "pagnotta"),
        category=BAKERY,
        days=2,
    ),
    pantry("pane integrale", "wholemeal bread", ("gluten",), category=BAKERY, days=3),
    pantry(
        "pane in cassetta",
        "sliced bread",
        ("gluten",),
        aliases=("pancarrè",),
        category=BAKERY,
        days=7,
    ),
    pantry("piadina", "piadina", ("gluten",), "pz", category=BAKERY, piece=100, days=7),
    pantry(
        "tortilla",
        "tortilla",
        ("gluten",),
        "pz",
        aliases=("wrap",),
        category=BAKERY,
        piece=60,
        days=7,
    ),
    pantry(
        "pasta sfoglia",
        "puff pastry",
        ("gluten", "milk"),
        "pz",
        ("rotolo di sfoglia",),
        category=BAKERY,
        piece=230,
        days=10,
    ),
    pantry(
        "pasta brisée",
        "shortcrust pastry",
        ("gluten", "milk"),
        "pz",
        category=BAKERY,
        piece=230,
        days=10,
    ),
    pantry("pangrattato", "breadcrumbs", ("gluten",), aliases=("pan grattato",)),
    # --- dispensa: pasta, riso, cereali ---
    pantry(
        "pasta",
        "pasta",
        ("gluten",),
        aliases=(
            "spaghetti",
            "penne",
            "fusilli",
            "rigatoni",
            "maccheroni",
            "linguine",
            "farfalle",
            "mezze maniche",
            "paccheri",
            "tagliatelle secche",
        ),
    ),
    pantry("pasta integrale", "wholemeal pasta", ("gluten",)),
    pantry(
        "pasta all'uovo",
        "egg pasta",
        ("gluten", "eggs"),
        aliases=("tagliatelle", "fettuccine", "pappardelle", "lasagne"),
    ),
    pantry("gnocchi di patate", "potato gnocchi", ("gluten",), aliases=("gnocchi",), days=10),
    pantry("tortellini", "tortellini", ("gluten", "eggs", "milk"), aliases=("ravioli",), days=10),
    pantry(
        "riso",
        "rice",
        aliases=("riso carnaroli", "riso arborio", "riso basmati", "riso integrale", "riso venere"),
    ),
    pantry("farro", "spelt", ("gluten",)),
    pantry("orzo perlato", "pearl barley", ("gluten",), aliases=("orzo",)),
    pantry("couscous", "couscous", ("gluten",), aliases=("cous cous",)),
    pantry("quinoa", "quinoa"),
    pantry("bulgur", "bulgur", ("gluten",)),
    pantry("polenta", "polenta", aliases=("farina di mais", "polenta istantanea")),
    pantry("fiocchi d'avena", "rolled oats", ("gluten",), aliases=("avena",)),
    pantry("farina 00", "plain flour", ("gluten",), aliases=("farina", "farina di grano tenero")),
    pantry("farina integrale", "wholemeal flour", ("gluten",)),
    pantry("semola", "semolina", ("gluten",), aliases=("semola rimacinata",)),
    pantry("amido di mais", "cornflour", aliases=("maizena", "fecola di patate", "fecola")),
    pantry("lievito di birra", "yeast", aliases=("lievito di birra secco",), days=14),
    pantry("lievito per dolci", "baking powder", aliases=("lievito chimico", "bicarbonato")),
    pantry("crackers", "crackers", ("gluten",), aliases=("cracker",)),
    pantry("gallette di riso", "rice cakes"),
    pantry("cereali", "breakfast cereals", ("gluten",), aliases=("muesli", "corn flakes")),
    pantry("fette biscottate", "rusks", ("gluten",)),
    pantry("biscotti", "biscuits", ("gluten", "milk", "eggs")),
    # --- dispensa: legumi ---
    pantry("ceci secchi", "dried chickpeas", aliases=("ceci",)),
    pantry("ceci in scatola", "canned chickpeas", aliases=("ceci lessati",)),
    pantry("fagioli secchi", "dried beans", aliases=("fagioli borlotti", "fagioli cannellini")),
    pantry(
        "fagioli in scatola",
        "canned beans",
        aliases=("fagioli lessati", "borlotti in scatola", "cannellini in scatola"),
    ),
    pantry("lenticchie", "lentils", aliases=("lenticchie rosse", "lenticchie secche")),
    pantry("piselli surgelati", "frozen peas", aliases=("piselli",), category=FROZEN),
    pantry("edamame", "edamame", ("soy",), category=FROZEN),
    pantry("tofu", "tofu", ("soy",), days=10),
    pantry("tempeh", "tempeh", ("soy",), days=10),
    # --- dispensa: conserve ---
    pantry("passata di pomodoro", "passata", unit="ml", aliases=("passata", "salsa di pomodoro")),
    pantry("pelati", "peeled tomatoes", aliases=("pomodori pelati", "polpa di pomodoro")),
    pantry("concentrato di pomodoro", "tomato paste", aliases=("doppio concentrato",)),
    pantry("tonno in scatola", "canned tuna", ("fish",), aliases=("tonno", "tonno sott'olio")),
    pantry("acciughe sott'olio", "anchovy fillets", ("fish",), aliases=("acciughe",)),
    pantry("olive", "olives", aliases=("olive nere", "olive verdi", "olive taggiasche")),
    pantry("capperi", "capers"),
    pantry("mais in scatola", "canned sweetcorn"),
    pantry("latte di cocco", "coconut milk", unit="ml"),
    pantry("brodo vegetale", "vegetable stock", ("celery",), "ml", ("dado vegetale", "brodo")),
    pantry("brodo di carne", "meat stock", ("celery",), "ml", ("dado di carne",)),
    # --- frutta secca e semi ---
    pantry("noci", "walnuts", ("nuts",), aliases=("gherigli di noce",)),
    pantry("mandorle", "almonds", ("nuts",), aliases=("farina di mandorle", "mandorle a lamelle")),
    pantry("nocciole", "hazelnuts", ("nuts",)),
    pantry("pistacchi", "pistachios", ("nuts",)),
    pantry("anacardi", "cashews", ("nuts",)),
    pantry("pinoli", "pine nuts", ("nuts",)),
    pantry("arachidi", "peanuts", ("peanuts",), aliases=("noccioline",)),
    pantry("burro di arachidi", "peanut butter", ("peanuts",)),
    pantry("semi di sesamo", "sesame seeds", ("sesame",), aliases=("sesamo",)),
    pantry("tahina", "tahini", ("sesame",), aliases=("tahin",)),
    pantry("semi di chia", "chia seeds"),
    pantry("semi di girasole", "sunflower seeds"),
    pantry("semi di zucca", "pumpkin seeds"),
    pantry("uvetta", "raisins", ("sulphites",), aliases=("uva passa",)),
    # --- dolci ---
    pantry("zucchero", "sugar", aliases=("zucchero semolato", "zucchero di canna"), staple=True),
    pantry("zucchero a velo", "icing sugar"),
    pantry("miele", "honey"),
    pantry("cioccolato fondente", "dark chocolate", ("milk", "soy"), aliases=("cioccolato",)),
    pantry("cacao amaro", "cocoa powder", aliases=("cacao",)),
    pantry("marmellata", "jam", aliases=("confettura",)),
    # --- spezie e condimenti ---
    spice("sale", "salt", aliases=("sale fino", "sale grosso")),
    spice("pepe nero", "black pepper", aliases=("pepe",)),
    spice(
        "olio extravergine d'oliva",
        "extra virgin olive oil",
        "ml",
        aliases=("olio evo", "olio d'oliva", "olio extravergine", "olio"),
    ),
    spice(
        "olio di semi", "seed oil", "ml", aliases=("olio di semi di girasole", "olio di arachidi")
    ),
    spice("aceto di vino", "wine vinegar", "ml", allergens=("sulphites",), aliases=("aceto",)),
    spice("aceto balsamico", "balsamic vinegar", "ml", allergens=("sulphites",)),
    spice("aceto di mele", "cider vinegar", "ml"),
    spice("salsa di soia", "soy sauce", "ml", allergens=("soy", "gluten"), aliases=("soia",)),
    spice("senape", "mustard", allergens=("mustard",)),
    spice("maionese", "mayonnaise", allergens=("eggs",), staple=False),
    spice("ketchup", "ketchup", staple=False),
    spice("peperoncino", "chilli flakes", aliases=("peperoncino secco", "peperoncino in polvere")),
    spice("paprika", "paprika", aliases=("paprika dolce", "paprika affumicata")),
    spice("curry", "curry powder"),
    spice("curcuma", "turmeric"),
    spice("cumino", "cumin"),
    spice("cannella", "cinnamon"),
    spice("noce moscata", "nutmeg"),
    spice("origano", "oregano"),
    spice("alloro", "bay leaves", aliases=("foglie di alloro",)),
    spice("zafferano", "saffron", staple=False),
    spice("vaniglia", "vanilla", aliases=("estratto di vaniglia", "vanillina")),
    spice("semi di finocchio", "fennel seeds"),
    # --- surgelati ---
    pantry(
        "verdure miste surgelate",
        "frozen mixed vegetables",
        aliases=("minestrone surgelato",),
        category=FROZEN,
    ),
    pantry("spinaci surgelati", "frozen spinach", category=FROZEN),
    pantry(
        "pesce surgelato", "frozen fish", ("fish",), aliases=("filetti surgelati",), category=FROZEN
    ),
    # --- bevande (in cucina) ---
    pantry("vino bianco", "white wine", ("sulphites",), "ml", category=DRINKS),
    pantry("vino rosso", "red wine", ("sulphites",), "ml", category=DRINKS),
    pantry("birra", "beer", ("gluten",), "ml", category=DRINKS),
    pantry(
        "bevanda di soia", "soy milk", ("soy",), "ml", ("latte di soia",), category=DRINKS, days=5
    ),
    pantry(
        "bevanda di mandorla",
        "almond milk",
        ("nuts",),
        "ml",
        ("latte di mandorla",),
        category=DRINKS,
        days=5,
    ),
    pantry(
        "bevanda d'avena",
        "oat milk",
        ("gluten",),
        "ml",
        ("latte d'avena",),
        category=DRINKS,
        days=5,
    ),
    pantry("acqua", "water", unit="ml", staple=True, category=DRINKS),
    pantry("caffè", "coffee", aliases=("caffe",), category=DRINKS),
]
