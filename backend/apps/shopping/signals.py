"""Un piano gia' mandato a Scontrino si rimanda quando cambiano i suoi pasti
(ADR 0026). La generazione scrive i pasti con ``bulk_create``, che non manda
segnali: li' si chiama ``schedule_push`` a mano."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.plans.models import PlannedMeal

from .scontrino import schedule_push


@receiver(post_save, sender=PlannedMeal)
def meal_saved(sender, instance, update_fields=None, **kwargs):
    # "Mangiato" non cambia la spesa.
    if update_fields and set(update_fields) <= {"eaten"}:
        return
    schedule_push(instance.plan_id)


@receiver(post_delete, sender=PlannedMeal)
def meal_deleted(sender, instance, **kwargs):
    schedule_push(instance.plan_id)
