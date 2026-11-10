"""Quando si cucina ogni pasto, secondo la modalita' di meal prep (codice, non LLM).

Si preparano in anticipo solo pranzo e cena: colazione e spuntini si fanno al
momento. Il risultato dice per ogni pasto quanti giorni deve reggere in frigo,
che l'LLM usa per scegliere le ricette e il codice per ricontrollarle.
"""

from __future__ import annotations

from datetime import date, timedelta

from apps.profiles.models import MEAL_SLOT_ORDER, MealSlot

from .models import PrepMode

PREPPED_SLOTS = {MealSlot.LUNCH, MealSlot.DINNER}
# Domenica e mercoledi': tre o quattro giorni di frigo al massimo.
WEEKEND_SESSIONS = {6, 2}


def plan_dates(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]


def cook_on(day: date, slot: str, *, start: date, mode: str) -> date:
    """Il giorno in cui si cucina il pasto ``slot`` di ``day``."""
    if slot not in PREPPED_SLOTS or mode == PrepMode.NONE:
        return day
    if mode == PrepMode.EVENING_BEFORE:
        # La sera prima si cucina anche il pranzo: la cena resta del giorno.
        return day - timedelta(days=1) if slot == MealSlot.LUNCH else day
    if mode in (PrepMode.EVERY_2, PrepMode.EVERY_3):
        block = 2 if mode == PrepMode.EVERY_2 else 3
        return start + timedelta(days=((day - start).days // block) * block)
    if mode == PrepMode.WEEKEND:
        # L'ultima domenica o mercoledi' che viene prima (o e') il giorno.
        candidate = day
        while candidate.weekday() not in WEEKEND_SESSIONS:
            candidate -= timedelta(days=1)
        return candidate
    return day


def schedule(start: date, days: list[date], slots: list[str], mode: str) -> list[dict]:
    """Un elemento per pasto: giorno, pasto, giorno di cottura, giorni di attesa."""
    ordered = sorted(slots, key=MEAL_SLOT_ORDER.index)
    out = []
    for day in days:
        for slot in ordered:
            cooked = cook_on(day, slot, start=start, mode=mode)
            out.append(
                {"date": day, "slot": slot, "cooked_on": cooked, "wait": (day - cooked).days}
            )
    return out
