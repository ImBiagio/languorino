"""Il piano alimentare dalle linee guida, per chi non ha un nutrizionista (ADR 0023).

"Cosa dovresti mangiare" ha la stessa forma del piano del nutrizionista
(``NutritionistRules``): per ogni pasto le opzioni con le grammature, le
frequenze a settimana, le sostituzioni, gli alimenti liberi. Cosi' la
revisione, la preparazione per ingredienti e la chat lo usano senza
distinzioni.

Le porzioni standard e le frequenze vengono dalle Linee guida per una sana
alimentazione del CREA (2018) e dalle raccomandazioni dell'OMS, scritte qui nel
prompt: l'LLM le adatta al profilo (eta', sesso, peso, attivita', obiettivi,
patologie, gusti) senza inventarsele. Nasce bozza: l'utente la rivede e la
conferma come quella del nutrizionista. Non e' un consiglio medico e lo dice.
"""

from __future__ import annotations

from django.utils.translation import gettext as _

from apps.ai.client import generate
from apps.profiles.models import MEAL_SLOT_ORDER, Profile
from apps.recipes.importing import LANGUAGES

from .generation import SLOT_NAMES, user_profile_summary
from .nutritionist import NutritionistReading, clean_rules

PROMPT = """Sei un dietista. Scrivi in {language} il piano alimentare settimanale di
riferimento per questa persona, seguendo le Linee guida per una sana alimentazione
del CREA (2018) e le raccomandazioni dell'OMS. Non e' una dieta medica: e' "cosa
dovrebbe mangiare" una persona sana con questo profilo. Rispondi solo col JSON.

{profile}

Pasti della sua giornata: {slots}.

Porzioni standard CREA (a persona, alimenti crudi e netti), da adattare al
fabbisogno della persona (piu' o meno porzioni, non grammature strane):
- cereali: pasta, riso, farro, orzo, cous cous 80 g; pane 50 g; fette biscottate
  o crackers 30 g; fiocchi d'avena 30 g; patate 200 g (contano come cereali)
- legumi: secchi 50 g, freschi o lessati 150 g
- pesce 150 g; carne bianca 100 g; carne rossa 100 g; uova 1 (60 g)
- latte e yogurt 125 ml/g; formaggio fresco 100 g, stagionato 50 g
- verdura 200 g (insalata 80 g); frutta 150 g; frutta secca 30 g
- olio extravergine 10 ml a porzione

Frequenze a settimana di riferimento (adattale al profilo):
- legumi 3-4 volte; pesce 2-3 volte; carne bianca 2-3 volte; carne rossa al
  massimo 1 volta; salumi al massimo 1 volta; uova 2-4 volte; formaggi 2-3 volte
- verdura a pranzo e a cena, frutta 2-3 volte al giorno, cereali integrali
  quando si puo'; sale poco (meno di 5 g al giorno, OMS); zuccheri liberi
  meno del 10% dell'energia, meglio sotto il 5% (OMS)

Come scriverlo:
- "meals": per ogni pasto della sua giornata, da 3 a 6 opzioni diverse,
  ognuna un pasto completo con alimenti e grammature a persona (es. "80 g pasta
  integrale + 150 g legumi lessati + 200 g verdura + 10 ml olio"). Pranzo e cena
  equilibrati: cereali, una fonte di proteine, verdura, olio. Alterna le fonti di
  proteine fra le opzioni.
- "weekly": le frequenze a settimana per legumi, pesce, carne bianca, carne
  rossa, uova, formaggi (e salumi se li prevedi), coi numeri adatti a lei.
- "substitutions": i gruppi di equivalenti con la grammatura di ciascuno (es.
  cereali: "80 g pasta", "80 g riso", "100 g pane", "200 g patate"; proteine:
  "150 g pesce", "100 g pollo", "2 uova", "150 g legumi lessati").
- "free_foods": verdure, erbe, spezie, acqua.
- "avoid_foods": SOLO cio' che la persona non deve mangiare (allergie,
  intolleranze, patologie), nomi brevi; vuoto se non c'e' niente.
- "notes": in due o tre frasi le indicazioni generali (acqua, sale, cotture,
  frutta) e che il piano e' indicativo: per esigenze di salute decide il medico
  o un nutrizionista.
- "title": "{title}". Date di validita' vuote, "problem" vuoto.

MAI alimenti che toccano le allergie e intolleranze del profilo, nemmeno nelle
sostituzioni. Rispetta i gusti quando puoi."""


def write_guidelines(user, language: str = "it") -> dict:
    """Le regole del piano dalle linee guida, gia' pulite come quelle lette."""
    profile, _forbidden = user_profile_summary(user)
    found = Profile.objects.filter(user=user).first()
    slots = [
        slot for slot in MEAL_SLOT_ORDER if found is None or slot in (found.meal_slots or [])
    ] or ["breakfast", "lunch", "dinner"]
    title = _("Piano dalle linee guida")
    prompt = PROMPT.format(
        language=LANGUAGES.get(language[:2], "italiano"),
        profile=profile,
        slots=", ".join(f"{SLOT_NAMES[slot]} [{slot}]" for slot in slots),
        title=title,
    )
    result, model = generate(
        [prompt],
        NutritionistReading,
        feature="diet_guidelines",
        user=user,
        timeout_ms=120_000,
        temperature=0.3,
    )
    rules = clean_rules(result)
    # Solo i pasti della sua giornata, anche se il modello ne aggiunge.
    rules["meals"] = [meal for meal in rules["meals"] if meal["slot"] in slots]
    return {
        "title": " ".join(result.title.split())[:120] or title,
        "rules": rules,
        "model": model,
    }
