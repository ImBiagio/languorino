"""Lista della spesa (progettazione 4.7, ADR 0008).

Una lista si genera dal piano (somma degli ingredienti dei pasti di un
intervallo di giorni) o si scrive a mano; le voci si spuntano. Il calcolo e'
tutto codice, niente LLM.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.recipes.models import Category, Unit


class ShoppingList(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Da fare")
        DONE = "done", _("Fatta")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shopping_lists"
    )
    title = models.CharField(max_length=120)
    plan = models.ForeignKey(
        "plans.MealPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    # Vuoto per le voci scritte a mano che non corrispondono al catalogo.
    ingredient = models.ForeignKey(
        "recipes.Ingredient", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    label = models.CharField(max_length=120)
    # Vuota per "q.b." o per le voci a mano senza quantita'.
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.OTHER)
    checked = models.BooleanField(default=False)
    # "Ce l'ho gia'": non va comprato (i basilari partono cosi').
    in_pantry = models.BooleanField(default=False)
    # Scritta a mano o modificata a mano: il ricalcolo dal piano non la tocca.
    manual = models.BooleanField(default=False)
    edited = models.BooleanField(default=False)
    # Da quali pasti viene: [{"date", "slot", "recipe"}], per spiegare il totale.
    sources = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"{self.label} {self.quantity or ''}{self.unit}"
