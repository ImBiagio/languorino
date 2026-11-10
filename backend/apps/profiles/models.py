"""Profilo alimentare: chi e' l'utente, cosa vuole ottenere, cosa non puo' mangiare.

E' l'ingresso di tutto il resto (piano, ricette proposte, "cosa cucino oggi").
Peso, altezza e patologie sono dati sanitari: restano qui e all'LLM ne arriva
solo la forma ridotta (progettazione, principio 4).
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel

from .allergens import Allergen


class Sex(models.TextChoices):
    FEMALE = "f", _("Donna")
    MALE = "m", _("Uomo")
    OTHER = "other", _("Preferisco non dirlo")


class Goal(models.TextChoices):
    LOSE_WEIGHT = "lose_weight", _("Perdere peso")
    GAIN_MUSCLE = "gain_muscle", _("Aumentare la massa muscolare")
    MAINTAIN = "maintain", _("Mantenere il peso")
    MORE_PROTEIN = "more_protein", _("Mangiare più proteine")
    EAT_BETTER = "eat_better", _("Mangiare più sano")
    MORE_VARIETY = "more_variety", _("Mangiare più vario")
    SAVE_TIME = "save_time", _("Perdere meno tempo in cucina")
    SAVE_MONEY = "save_money", _("Spendere meno")


class ActivityLevel(models.TextChoices):
    SEDENTARY = "sedentary", _("Sedentario")
    LIGHT = "light", _("Leggero")
    MODERATE = "moderate", _("Moderato")
    INTENSE = "intense", _("Intenso")


class MealSlot(models.TextChoices):
    BREAKFAST = "breakfast", _("Colazione")
    MORNING_SNACK = "morning_snack", _("Spuntino di metà mattina")
    LUNCH = "lunch", _("Pranzo")
    AFTERNOON_SNACK = "afternoon_snack", _("Merenda")
    DINNER = "dinner", _("Cena")


# In ordine di giornata: le liste di pasti si salvano sempre cosi'.
MEAL_SLOT_ORDER = [slot.value for slot in MealSlot]


def default_meal_slots() -> list[str]:
    return [MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER]


class Profile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="food_profile"
    )
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=8, choices=Sex.choices, blank=True)
    height_cm = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(80), MaxValueValidator(250)]
    )
    weight_kg = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(20), MaxValueValidator(350)],
    )
    goals = ArrayField(
        models.CharField(max_length=20, choices=Goal.choices), default=list, blank=True
    )
    # Quello che le scelte non dicono ("arrivare alla maratona di aprile").
    goals_note = models.TextField(blank=True, max_length=1000)
    activity_level = models.CharField(max_length=12, choices=ActivityLevel.choices, blank=True)
    sport_sessions_per_week = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(14)]
    )
    # Patologie in testo libero: troppo varie per una lista chiusa.
    conditions = ArrayField(models.CharField(max_length=120), default=list, blank=True)
    # None finche' non ha risposto: decide quale strada prende il piano.
    followed_by_nutritionist = models.BooleanField(null=True, blank=True)
    meal_slots = ArrayField(
        models.CharField(max_length=16, choices=MealSlot.choices),
        default=default_meal_slots,
        blank=True,
    )
    # Per quante persone si cucina di solito: moltiplica porzioni e spesa.
    household_size = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    # Vuoto: l'app apre il wizard al posto della home.
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Profilo di {self.user}"

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = date.today()
        before_birthday = (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        return today.year - self.birth_date.year - int(before_birthday)


class FoodPreference(BaseModel):
    """Una cosa che piace, non piace, o che non si puo' mangiare."""

    class Kind(models.TextChoices):
        LIKE = "like", _("Mi piace")
        DISLIKE = "dislike", _("Non mi piace")
        ALLERGY = "allergy", _("Allergia")
        INTOLERANCE = "intolerance", _("Intolleranza")

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="preferences")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    label = models.CharField(max_length=80)
    # Collegato quando l'etichetta corrisponde a uno dei 14 allergeni UE: e'
    # quello che useranno i controlli sulle ricette.
    allergen = models.CharField(max_length=12, choices=Allergen.choices, blank=True)

    class Meta:
        ordering = ["kind", "label"]
        constraints = [
            # Le preferenze si cancellano davvero (hard delete): il vincolo vale
            # su tutte le righe.
            models.UniqueConstraint(
                "profile", "kind", Lower("label"), name="unique_preference_per_kind"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.label}"

    @property
    def is_restriction(self) -> bool:
        """Allergie e intolleranze sono vincoli, non gusti."""
        return self.kind in {self.Kind.ALLERGY, self.Kind.INTOLERANCE}
