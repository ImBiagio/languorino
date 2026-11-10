"""I 14 allergeni da dichiarare per legge nell'UE (Reg. 1169/2011, allegato II).

Sono la base dei controlli di sicurezza del piano (progettazione, principio 2):
un'allergia scritta a mano ("gamberi", "nocciole") si collega qui al suo
allergene, cosi' piu' avanti si potranno scartare le ricette con un ingrediente
che lo contiene senza affidarsi all'LLM.

Il riconoscimento e' per parole chiave e volutamente prudente: se non c'e' una
corrispondenza sicura l'allergene resta vuoto e l'etichetta vale come testo.
"""

from __future__ import annotations

import re
import unicodedata

from django.db import models
from django.utils.translation import gettext_lazy as _


class Allergen(models.TextChoices):
    GLUTEN = "gluten", _("Glutine")
    CRUSTACEANS = "crustaceans", _("Crostacei")
    EGGS = "eggs", _("Uova")
    FISH = "fish", _("Pesce")
    PEANUTS = "peanuts", _("Arachidi")
    SOY = "soy", _("Soia")
    MILK = "milk", _("Latte e lattosio")
    NUTS = "nuts", _("Frutta a guscio")
    CELERY = "celery", _("Sedano")
    MUSTARD = "mustard", _("Senape")
    SESAME = "sesame", _("Sesamo")
    SULPHITES = "sulphites", _("Solfiti")
    LUPIN = "lupin", _("Lupini")
    MOLLUSCS = "molluscs", _("Molluschi")


# Radici delle parole, senza accenti e in minuscolo: "gamber" prende gambero,
# gamberi e gamberetti. Italiano e inglese, perche' l'interfaccia e' in due lingue.
KEYWORDS: dict[str, tuple[str, ...]] = {
    Allergen.GLUTEN: (
        "glutin",
        "gluten",
        "frument",
        "grano",
        "orz",
        "segale",
        "farro",
        "kamut",
        "celiac",
        "wheat",
        "barley",
        "rye",
        "spelt",
    ),
    Allergen.CRUSTACEANS: (
        "crostace",
        "gamber",
        "scamp",
        "aragost",
        "astice",
        "granchi",
        "mazzancoll",
        "shrimp",
        "prawn",
        "lobster",
        "crab",
        "crustacean",
    ),
    Allergen.EGGS: ("uov", "uovo", "egg"),
    Allergen.FISH: (
        "pesce",
        "pesci",
        "tonno",
        "salmon",
        "merluzz",
        "acciug",
        "alici",
        "sardin",
        "fish",
        "tuna",
        "cod",
        "anchov",
    ),
    Allergen.PEANUTS: ("arachid", "nocciolin", "peanut"),
    Allergen.SOY: ("soia", "soy", "tofu", "edamame"),
    Allergen.MILK: (
        "latte",
        "lattos",
        "latticin",
        "formagg",
        "burro",
        "panna",
        "yogurt",
        "caseina",
        "milk",
        "lactose",
        "dairy",
        "cheese",
        "butter",
        "cream",
    ),
    Allergen.NUTS: (
        "frutta a guscio",
        "noci",
        "noce",
        "nocciola",
        "nocciole",
        "mandorl",
        "pistacch",
        "anacard",
        "pinol",
        "macadamia",
        "pecan",
        "nut",
        "almond",
        "hazelnut",
        "walnut",
        "cashew",
        "pistachio",
    ),
    Allergen.CELERY: ("sedan", "celery"),
    Allergen.MUSTARD: ("senap", "mustard"),
    Allergen.SESAME: ("sesam", "tahin"),
    Allergen.SULPHITES: ("solfit", "sulphit", "sulfit", "anidride solforosa"),
    Allergen.LUPIN: ("lupin",),
    Allergen.MOLLUSCS: (
        "mollusc",
        "cozz",
        "vongol",
        "calamar",
        "polpo",
        "polpi",
        "seppi",
        "ostrich",
        "mussel",
        "clam",
        "squid",
        "octopus",
        "oyster",
        "mollusk",
    ),
}

# "Noce moscata" non e' frutta a guscio, "latte di cocco" non e' latte: le
# eccezioni note vincono sulle parole chiave.
EXCEPTIONS = (
    "noce moscata",
    "nutmeg",
    "latte di cocco",
    "coconut milk",
    "burro di cacao",
    "cocoa butter",
    "latte di mandorl",
    "almond milk",
    "latte di soia",
    "soy milk",
    "granoturco",
    "grano saraceno",
    "buckwheat",
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).strip()


def detect_allergen(label: str) -> str:
    """L'allergene di un'etichetta scritta a mano, o ``""`` se non e' chiaro.

    Si guarda prima il nome esatto dell'allergene ("Glutine"), poi le parole
    chiave a inizio parola. Se l'etichetta ne tocca piu' d'uno (es. "pesce e
    gamberi") non si sceglie: meglio niente che quello sbagliato.
    """
    text = _normalize(label)
    if not text:
        return ""
    for value, name in Allergen.choices:
        if text in {value, _normalize(str(name))}:
            return value
    if any(exception in text for exception in EXCEPTIONS):
        # Le bevande vegetali restano a chi le contiene davvero (mandorla, soia).
        for allergen, word in (
            (Allergen.NUTS, "mandorl"),
            (Allergen.SOY, "soia"),
            (Allergen.NUTS, "almond"),
            (Allergen.SOY, "soy"),
        ):
            if word in text:
                return allergen
        return ""
    found = {
        allergen
        for allergen, words in KEYWORDS.items()
        if any(re.search(rf"\b{re.escape(word)}", text) for word in words)
    }
    return found.pop() if len(found) == 1 else ""
