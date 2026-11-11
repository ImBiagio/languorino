"""Piano alimentare (progettazione 4.3 e 4.4, ADR 0007).

Un piano copre da 7 a 28 giorni e si genera una settimana alla volta, come i
ricettari PDF si leggono a pezzi. Ogni pasto sa in che giorno si cucina
(``cooked_on``): uguale al giorno in cui si mangia, o prima se viene dal meal
prep. "Cosa cucini" non e' un modello a parte: sono i pasti raggruppati per
``cooked_on``.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.profiles.models import MealSlot


class PrepMode(models.TextChoices):
    NONE = "none", _("Cucino al momento")
    EVENING_BEFORE = "evening_before", _("La sera cucino anche il pranzo del giorno dopo")
    EVERY_2 = "every_2", _("Cucino ogni 2 giorni")
    EVERY_3 = "every_3", _("Cucino ogni 3 giorni")
    WEEKEND = "weekend", _("Domenica e mercoledì per tutta la settimana")


class MealPlan(BaseModel):
    class Status(models.TextChoices):
        GENERATING = "generating", _("In preparazione")
        DRAFT = "draft", _("Da attivare")
        ACTIVE = "active", _("Attivo")
        ARCHIVED = "archived", _("Archiviato")
        FAILED = "failed", _("Interrotto")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meal_plans"
    )
    start_date = models.DateField()
    days = models.PositiveSmallIntegerField(default=7)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.GENERATING, db_index=True
    )
    # Le scelte fatte creando il piano (pasti, porzioni, prep, fonti, tag,
    # obiettivo): servono per generarlo e per rifarlo uguale.
    settings = models.JSONField(default=dict)
    weeks_done = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    language = models.CharField(max_length=8, default="it")
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self) -> str:
        return f"Piano dal {self.start_date} ({self.days} giorni)"

    @property
    def weeks_total(self) -> int:
        return (self.days + 6) // 7


def current_plan(owner, today: date | None = None) -> MealPlan | None:
    """Il piano attivo che copre oggi; altrimenti il prossimo che deve iniziare.

    E' il piano della home "Oggi" e quello di cui parla la chat (ADR 0016).
    """
    today = today or date.today()
    active = MealPlan.objects.filter(owner=owner, status=MealPlan.Status.ACTIVE)
    for plan in active:
        if plan.start_date <= today < plan.start_date + timedelta(days=plan.days):
            return plan
    return active.filter(start_date__gt=today).order_by("start_date").first()


class PlannedMeal(models.Model):
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="meals")
    date = models.DateField()
    slot = models.CharField(max_length=16, choices=MealSlot.choices)
    # Vuoto se non si e' trovato niente di adatto (o la ricetta e' stata scartata).
    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    servings = models.PositiveSmallIntegerField(default=1)
    # Il giorno in cui si cucina: prima di ``date`` se viene dal meal prep.
    cooked_on = models.DateField()
    # Perche' il pasto e' vuoto o e' stato cambiato (mostrato all'utente).
    note = models.CharField(max_length=200, blank=True)
    eaten = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "slot"]
        constraints = [
            models.UniqueConstraint("plan", "date", "slot", name="one_meal_per_slot"),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.slot}: {self.recipe or '—'}"


class NutritionistPlan(BaseModel):
    """Il piano del nutrizionista letto da PDF o foto (progettazione 4.3, ADR 0010).

    Nasce bozza dalla lettura dell'LLM e vale solo dopo la conferma. ``rules``
    ha la forma di ``nutritionist.NutritionistRules``: per ogni pasto le
    opzioni con le grammature, le frequenze a settimana, gli alimenti liberi e
    quelli da evitare. I file originali restano col job che li ha letti.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Da rivedere")
        CONFIRMED = "confirmed", _("Confermato")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nutritionist_plans"
    )
    job = models.OneToOneField(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nutritionist_plan",
    )
    title = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    # Alla lettera: il piano usa solo le opzioni del nutrizionista. Altrimenti
    # ricette equivalenti con le stesse grammature e frequenze.
    strict = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    rules = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
