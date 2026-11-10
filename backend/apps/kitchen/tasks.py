from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.plans.models import PlannedMeal
from apps.recipes.models import Recipe

# Quanto resta un'idea di "cosa cucino oggi" mai salvata.
IDEAS_KEEP_DAYS = 7


@shared_task
def clean_ideas() -> int:
    """Via le idee mai salvate dopo una settimana (ADR 0009).

    Ogni ricerca ne scrive due: senza pulizia si accumulerebbero fuori dal
    ricettario. Restano quelle salvate e quelle finite in un piano.
    """
    old = timezone.now() - timedelta(days=IDEAS_KEEP_DAYS)
    stale = Recipe.objects.filter(
        source=Recipe.Source.FRIDGE,
        in_cookbook=False,
        book__isnull=True,
        created_at__lt=old,
    ).exclude(id__in=PlannedMeal.objects.filter(recipe__isnull=False).values("recipe_id"))
    count = 0
    for recipe in stale:
        recipe.delete(hard=True)
        count += 1
    return count
