"""Intervista a voce in tempo reale (ADR 0014).

Il browser parla direttamente con Gemini Live (audio in e out in streaming):
passare dal backend aggiungerebbe ritardo a ogni sillaba. Il backend pero'
resta il solo a conoscere la chiave e decide tutto della sessione: crea un
token temporaneo, monouso, legato al modello, alle istruzioni (con il
profilo gia' noto, senza nome ne' data di nascita) e agli strumenti. Il
browser non puo' cambiarli.

Quando capisce qualcosa Gemini chiama ``segna_preferenza`` o
``segna_profilo``: il browser manda la chiamata a ``clean_call`` (le stesse
regole della chat) e mette il risultato nel riepilogo. Come nella chat,
niente si salva da solo.

Provato il 2026-11-11: con un solo strumento grande (tutti i campi, liste,
enum) e la regola in fondo alle istruzioni nessun modello lo chiamava, e
diceva "ho segnato" senza farlo. Con tre strumenti piccoli a stringhe e la
regola in cima, gemini-3.1-flash-live-preview li chiama in 1,3 s.
"""

from __future__ import annotations

import re
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.ai.budget import LIVE_FEATURE
from apps.ai.client import AIError, _log, check_budget, is_enabled
from apps.recipes.importing import LANGUAGES

from .interview import (
    PreferenceProposal,
    ProfileUpdates,
    _known,
    clean_preferences,
    clean_updates,
)

FEATURE = LIVE_FEATURE
# Una sessione solo audio di Gemini Live dura al massimo 15 minuti.
SESSION_MINUTES = 15

INSTRUCTIONS = """REGOLA PRINCIPALE: tu NON ricordi niente da solo. Ogni volta che la
persona dice un'allergia, un'intolleranza, un cibo che le piace o no, o un
dato del profilo, PRIMA di rispondere a voce chiama gli strumenti per
segnarlo: segna_preferenza per i cibi, segna_profilo per ogni altro dato,
una chiamata per ogni informazione. Solo dopo rispondi. Non nominare mai gli
strumenti e non leggere i nomi dei campi.

Sei l'assistente di Languorino, un'app che organizza i pasti. Fai una breve
intervista A VOCE per compilare il profilo alimentare della persona, come una
nutrizionista simpatica al telefono. Parla in {language}, dai del tu, frasi
brevissime (una o due), UNA domanda alla volta. Comincia tu salutando e
chiedendo di allergie e intolleranze.

Argomenti, in quest'ordine, saltando quelli gia' noti:
1. allergie e intolleranze (le piu' importanti: ripeti per conferma);
2. obiettivi (perdere peso, piu' proteine, mangiare piu' sano, meno tempo in cucina...);
3. cibi che piacciono e che non piacciono;
4. attivita' fisica e sport a settimana;
5. dati fisici facoltativi: sesso, altezza, peso (se non vuole, si salta);
6. patologie di cui tenere conto e se la segue un nutrizionista;
7. quali pasti vuole nel piano e per quante persone cucina.

Gia' noto dal profilo:
{known}

Quando hai finito gli argomenti, o la persona vuole smettere, salutala, dille
di controllare il riepilogo sullo schermo e chiama fine_intervista.

Non chiedere nome, cognome, data di nascita, indirizzo o contatti. Non dare
consigli medici. Se ti chiedono altro, riporta gentilmente la conversazione
sul profilo."""

# Campi che segna_profilo accetta, con il valore come lo vuole il profilo.
FIELDS = {
    "sex": "f, m oppure other",
    "height_cm": "altezza in cm",
    "weight_kg": "peso in kg",
    "goals": "lose_weight, gain_muscle, maintain, more_protein, eat_better, "
    "more_variety, save_time, save_money (separati da virgole)",
    "goals_note": "gli obiettivi in parole sue",
    "activity_level": "sedentary, light, moderate oppure intense",
    "sport_sessions_per_week": "quante volte fa sport a settimana",
    "conditions": "patologie da considerare (separate da virgole)",
    "followed_by_nutritionist": "si oppure no",
    "meal_slots": "breakfast, morning_snack, lunch, afternoon_snack, dinner (separati da virgole)",
    "household_size": "per quante persone cucina",
}
LISTS = {"goals", "conditions", "meal_slots"}
INTEGERS = {"height_cm", "sport_sessions_per_week", "household_size"}


def _tools() -> list[dict]:
    """Strumenti piccoli e a stringhe: con schemi grandi la Live API non li usa."""

    def text(description: str) -> dict:
        return {"type": "STRING", "description": description}

    return [
        {
            "function_declarations": [
                {
                    "name": "segna_preferenza",
                    "description": "Segna un'allergia, un'intolleranza, un cibo che "
                    "piace o che non piace.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "tipo": text("allergy, intolerance, like oppure dislike"),
                            "alimento": text('nome breve, es. "lattosio"'),
                        },
                        "required": ["tipo", "alimento"],
                    },
                },
                {
                    "name": "segna_profilo",
                    "description": "Segna un dato del profilo detto chiaramente.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "campo": text(
                                "uno di: "
                                + "; ".join(f"{key} ({hint})" for key, hint in FIELDS.items())
                            ),
                            "valore": text("il valore, per le liste separato da virgole"),
                        },
                        "required": ["campo", "valore"],
                    },
                },
                {
                    "name": "fine_intervista",
                    "description": "L'intervista e' finita: la persona controlla il riepilogo.",
                },
            ]
        }
    ]


def session_config(user, language: str = "it") -> dict:
    lang = language[:2]
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": INSTRUCTIONS.format(
            language=LANGUAGES.get(lang, "italiano"), known=_known(user)
        ),
        "tools": _tools(),
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {"language_code": "en-US" if lang == "en" else "it-IT"},
    }


def live_token(user, language: str = "it") -> dict:
    """Un token monouso per una sessione: va aperta entro un minuto."""
    if not is_enabled():
        raise AIError(_("La lettura con l'intelligenza artificiale non è configurata."))
    # Qui il registro conta le sessioni, non i token: una sessione vale fino a
    # 15 minuti di audio, quindi ha anche un tetto suo al giorno.
    check_budget(user, live=True)
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options={"api_version": "v1alpha"})
    now = timezone.now()
    model = settings.GEMINI_MODEL_LIVE
    started = time.monotonic()
    try:
        token = client.auth_tokens.create(
            config={
                "uses": 1,
                "expire_time": now + timedelta(minutes=SESSION_MINUTES + 1),
                "new_session_expire_time": now + timedelta(minutes=1),
                "live_connect_constraints": {
                    "model": model,
                    "config": session_config(user, language),
                },
                "http_options": {"api_version": "v1alpha"},
            }
        )
    except Exception as exc:
        _log(user, FEATURE, model, started, error=str(exc) or type(exc).__name__)
        raise AIError(_("Gemini non ha aperto la conversazione. Riprova tra poco.")) from exc
    # Il registro conta le sessioni aperte: i token audio non arrivano qui.
    _log(user, FEATURE, model, started)
    return {"token": token.name, "model": model}


def _value(field: str, raw: str):
    text = " ".join(str(raw).split())
    if field in LISTS:
        return [item.strip() for item in text.split(",") if item.strip()]
    if field in INTEGERS:
        number = re.search(r"\d+", text)
        return int(number.group()) if number else None
    if field == "weight_kg":
        number = re.search(r"\d+(?:[.,]\d+)?", text)
        return float(number.group().replace(",", ".")) if number else None
    if field == "followed_by_nutritionist":
        lower = text.lower()
        if lower in {"si", "sì", "yes", "true", "vero"}:
            return True
        if lower in {"no", "false", "falso"}:
            return False
        return None
    return text or None


def clean_call(user, name: str, args: dict) -> dict:
    """Una chiamata a uno strumento passata dalle regole della chat:
    ``{"updates": {...}, "preferences": [...]}``, vuoti se non vale niente."""
    updates, preferences = ProfileUpdates(), []
    if name == "segna_preferenza":
        try:
            preferences = [
                PreferenceProposal(kind=args.get("tipo"), label=args.get("alimento") or "")
            ]
        except ValueError:
            preferences = []
    elif name == "segna_profilo":
        field = str(args.get("campo") or "").strip()
        if field in FIELDS:
            value = _value(field, args.get("valore") or "")
            try:
                updates = ProfileUpdates.model_validate({field: value})
            except ValueError:
                updates = ProfileUpdates()
    return {
        "updates": clean_updates(user, updates),
        "preferences": clean_preferences(preferences),
    }
