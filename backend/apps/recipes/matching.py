"""Riconoscere un ingrediente dal nome scritto a mano.

"Zucchine", "zucchina" e "Zucchìne " devono finire sullo stesso ingrediente
del catalogo: per sommare la spesa, per gli allergeni e per capire se una
ricetta contiene qualcosa che non piace. Si confrontano chiavi normalizzate
(minuscole, senza accenti e spazi doppi) e qualche variante di singolare e
plurale italiano; niente LLM.
"""

from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.replace("\u2019", "'").split())


# Finali del singolare e del plurale italiani piu' comuni: "carota" <-> "carote",
# "pomodoro" <-> "pomodori", "peperone" <-> "peperoni", "radicchio" <-> "radicchi".
_ENDINGS = [
    ("a", "e"),
    ("o", "i"),
    ("e", "i"),
    ("io", "i"),
    ("ca", "che"),
    ("ga", "ghe"),
    ("co", "chi"),
    ("go", "ghi"),
]


def _word_variants(word: str) -> list[str]:
    out = [word]
    for singular, plural in _ENDINGS:
        for src, dst in ((singular, plural), (plural, singular)):
            if word.endswith(src) and len(word) > len(src) + 2:
                candidate = word[: -len(src)] + dst
                if candidate not in out:
                    out.append(candidate)
    return out


MAX_VARIANTS = 24


def variants(text: str) -> list[str]:
    """La chiave normalizzata e le varianti singolare/plurale di ogni parola.

    "peperoni rossi" prova anche "peperone rosso"; la prima e' sempre la
    chiave cosi' com'e'. Le combinazioni hanno un tetto: i nomi sono corti.
    """
    key = normalize(text)
    if not key:
        return []
    combos = [""]
    for word in key.split(" "):
        options = _word_variants(word) if len(word) > 3 else [word]
        combos = [f"{head} {option}".strip() for head in combos for option in options]
        combos = combos[:MAX_VARIANTS]
    return [key, *[combo for combo in combos if combo != key]]


# Parole di preparazione che a volte restano attaccate al nome ("parmigiano
# grattugiato", "cipolla tritata"): se il nome intero non e' nel catalogo si
# riprova senza, in fondo al nome. Solo queste: "macinato misto" e "latte di
# cocco" sono nomi veri e non si accorciano.
PREPARATION_WORDS = {
    "grattugiato",
    "grattugiata",
    "grattugiati",
    "grattugiate",
    "tritato",
    "tritata",
    "tritati",
    "tritate",
    "fresco",
    "fresca",
    "freschi",
    "fresche",
    "affettato",
    "affettata",
    "affettati",
    "affettate",
    "sbucciato",
    "sbucciata",
    "sbucciati",
    "sbucciate",
    "tagliato",
    "tagliata",
    "tagliati",
    "tagliate",
    "lessato",
    "lessata",
    "lessati",
    "lessate",
    "sminuzzato",
    "sminuzzata",
    "spezzettato",
    "spezzettata",
    "ammollato",
    "ammollati",
    "sgocciolato",
    "sgocciolati",
    "grated",
    "chopped",
    "fresh",
    "sliced",
    "diced",
    "peeled",
    "minced",
}


def without_preparation(text: str) -> str | None:
    """Il nome senza le parole di preparazione in fondo, o None se non cambia."""
    words = normalize(text).split(" ")
    while len(words) > 1 and words[-1] in PREPARATION_WORDS:
        words.pop()
    shorter = " ".join(words)
    return shorter if shorter != normalize(text) else None


def keys_for(*names: str) -> list[str]:
    """Le chiavi di ricerca di un ingrediente: nome, nome inglese, sinonimi."""
    keys: list[str] = []
    for name in names:
        key = normalize(name)
        if key and key not in keys:
            keys.append(key)
    return keys
