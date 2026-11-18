"""Gli alimenti del piano alimentare e i pasti a cui appartengono (ADR 0023).

Un piano del nutrizionista ha le opzioni di tutti i pasti della giornata, ma la
preparazione spesso cucina solo pranzi e cene. Gli alimenti di colazione,
spuntini e merende (yogurt, frutta, frutta secca, crackers...) non devono
finire a pranzo o a cena: succedeva perche' le frequenze del piano ("yogurt 3
volte a settimana") si contavano sui pasti preparati, e l'LLM ci metteva lo
yogurt per farle tornare (2026-11-18).

Qui il codice decide, sul testo del piano:

- quali alimenti "da colazione o merenda" il piano non prevede a pranzo e cena
  (``side_only_foods``): si tolgono dai pasti principali composti dall'LLM;
- quali frequenze contano nei pasti preparati (``prepared_weekly``): quelle di
  quegli alimenti no, se colazione e spuntini non si preparano;
- quali regole vede l'LLM (``prepared_rules``): solo i pasti preparati.

Niente import dal resto di ``plans``: ``nutritionist`` e ``generation`` usano
questo modulo, e fra loro si importano gia'.
"""

from __future__ import annotations

from apps.recipes.matching import _word_variants, normalize

MAIN_SLOTS = ("lunch", "dinner")
SIDE_SLOTS = ("breakfast", "morning_snack", "afternoon_snack")

# Parole che non dicono quale alimento e': "petto di pollo" e' "pollo".
STOP_WORDS = {"di", "del", "della", "al", "alla", "con", "e", "in", "a", "da"}

# Gli alimenti tipici di colazione e merenda. Valgono solo se il piano non li
# mette anche a pranzo o a cena (opzioni o sostituzioni di quei pasti).
SIDE_FOODS = [
    "yogurt",
    "latte",
    "kefir",
    "skyr",
    "cereali da colazione",
    "muesli",
    "granola",
    "corn flakes",
    "biscotti",
    "fette biscottate",
    "marmellata",
    "confettura",
    "miele",
    "crema spalmabile",
    "crema di frutta secca",
    "burro di arachidi",
    "frutta secca",
    "mandorle",
    "noci",
    "nocciole",
    "pistacchi",
    "anacardi",
    "arachidi",
    "frutta",
    "frutto",
    "mela",
    "banana",
    "pera",
    "arancia",
    "mandarino",
    "kiwi",
    "fragole",
    "frutti di bosco",
    "crackers",
    "cracker",
    "gallette",
    "grissini",
    "taralli",
    "cioccolato",
    "barretta",
    "spremuta",
    "succo",
    "tisana",
]

# Nomi che contengono un alimento da merenda ma sono altro.
NOT_SIDE = ["fiocchi di latte", "frutti di mare", "latte di cocco", "noce moscata"]

# Le parole delle note delle sostituzioni ("a merenda", "a pranzo").
NOTE_SLOTS = {
    "colazione": "breakfast",
    "spuntino": "morning_snack",
    "spuntini": "morning_snack",
    "merenda": "afternoon_snack",
    "merende": "afternoon_snack",
    "pranzo": "lunch",
    "pranzi": "lunch",
    "cena": "dinner",
    "cene": "dinner",
}


def words(text: str) -> set[str]:
    """Le parole del testo con singolare e plurale, senza articoli e preposizioni."""
    out = set()
    for word in normalize(text).replace("'", " ").split():
        if word not in STOP_WORDS:
            out.update(_word_variants(word))
    return out


def same_food(line_name: str, equivalent_name: str) -> bool:
    """ "pasta integrale" e' "pasta", "petto di pollo" e' "pollo", "couscous" e'
    "cous cous": tutte le parole dell'equivalente stanno nel nome del pasto."""
    if normalize(line_name).replace(" ", "") == normalize(equivalent_name).replace(" ", ""):
        return True
    wanted = set(normalize(equivalent_name).replace("'", " ").split())
    wanted -= STOP_WORDS
    have = words(line_name)
    return bool(wanted) and all(set(_word_variants(word)) & have for word in wanted)


def note_slots(note: str) -> set[str]:
    """I pasti nominati nella nota di una sostituzione ("a merenda")."""
    return {NOTE_SLOTS[word] for word in normalize(note).split() if word in NOTE_SLOTS}


def _group_slots(group: dict) -> set[str]:
    """I pasti a cui vale un gruppo di sostituzioni: quelli della nota, o tutti."""
    return note_slots(group.get("note", "")) or set(MAIN_SLOTS + SIDE_SLOTS)


def main_words(rules: dict) -> set[str]:
    """Le parole degli alimenti che il piano prevede a pranzo e a cena."""
    texts = [
        option
        for meal in rules.get("meals", [])
        if meal["slot"] in MAIN_SLOTS
        for option in meal["options"]
    ]
    for group in rules.get("substitutions", []):
        if _group_slots(group) & set(MAIN_SLOTS):
            texts.extend(group["equivalents"])
    return words(" ".join(texts))


def side_only_foods(rules: dict) -> list[str]:
    """Gli alimenti da colazione e merenda che il piano non prevede a pranzo e
    a cena. Senza piano (o senza pasti principali) valgono tutti."""
    have = main_words(rules)
    return [
        food
        for food in SIDE_FOODS
        if not all(set(_word_variants(word)) & have for word in words_of(food))
    ]


def words_of(food: str) -> list[str]:
    return [word for word in normalize(food).split() if word not in STOP_WORDS]


def is_side_food(name: str, side_foods: list[str]) -> bool:
    """Se l'alimento e' uno di quelli da colazione o merenda."""
    if any(same_food(name, other) for other in NOT_SIDE):
        return False
    return any(same_food(name, food) for food in side_foods)


def prepared_weekly(rules: dict, slots: list[str] | None) -> list[dict]:
    """Le frequenze che contano nei pasti preparati: senza colazione e spuntini
    si tolgono quelle degli alimenti da merenda ("yogurt 3 volte")."""
    weekly = rules.get("weekly", [])
    if slots is None or set(slots) & set(SIDE_SLOTS):
        return weekly
    side = side_only_foods(rules)
    return [item for item in weekly if not is_side_food(item["food"], side)]


def prepared_rules(rules: dict, slots: list[str] | None) -> dict:
    """Le regole del piano ridotte ai pasti che si preparano: l'LLM non vede le
    opzioni della merenda se cucina solo pranzi e cene."""
    if not slots:
        return rules
    wanted = set(slots)
    return {
        **rules,
        "meals": [meal for meal in rules.get("meals", []) if meal["slot"] in wanted],
        "substitutions": [
            group for group in rules.get("substitutions", []) if _group_slots(group) & wanted
        ],
        "weekly": prepared_weekly(rules, slots),
    }


def plan_side_foods(rules: dict) -> list[str]:
    """Gli alimenti da colazione e merenda che il piano nomina davvero (per il
    prompt: "niente yogurt, frutta secca, crackers a pranzo e a cena")."""
    texts = [
        option
        for meal in rules.get("meals", [])
        if meal["slot"] in SIDE_SLOTS
        for option in meal["options"]
    ]
    have = words(" ".join(texts))
    return [
        food
        for food in side_only_foods(rules)
        if all(set(_word_variants(word)) & have for word in words_of(food))
    ]


def side_rule(rules: dict) -> str:
    """La riga del prompt che tiene fuori da pranzo e cena gli alimenti da merenda."""
    named = plan_side_foods(rules) or ["yogurt", "latte", "frutta", "frutta secca", "crackers"]
    return (
        "- A pranzo e a cena MAI gli alimenti di colazione, spuntini e merende ("
        + ", ".join(named[:10])
        + "), nemmeno per far tornare le frequenze: nei pasti principali solo gli "
        "alimenti delle loro opzioni e sostituzioni."
    )
