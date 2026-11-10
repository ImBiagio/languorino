"""Carica o aggiorna il catalogo degli ingredienti (migrazione e comando)."""

from __future__ import annotations

from .catalog import CATALOG
from .matching import keys_for


def load_catalog(ingredient_model) -> tuple[int, int]:
    """Crea gli ingredienti mancanti e aggiorna gli altri. Restituisce (creati, aggiornati).

    Riceve il modello come argomento perche' la migrazione deve usare quello
    storico (``apps.get_model``), non quello del codice attuale.
    """
    created = updated = 0
    existing = {
        item.name.lower(): item for item in ingredient_model.objects.filter(created_by__isnull=True)
    }
    for entry in CATALOG:
        keys = keys_for(entry.name, entry.name_en, *entry.aliases)
        values = {
            "name": entry.name,
            "name_en": entry.name_en,
            "keys": keys,
            "search_text": " | ".join(keys),
            "category": entry.category,
            "allergens": list(entry.allergens),
            "default_unit": entry.unit,
            "grams_per_piece": entry.grams_per_piece,
            "perishable_days": entry.perishable_days,
            "staple": entry.staple,
        }
        item = existing.get(entry.name.lower())
        if item is None:
            ingredient_model.objects.create(**values)
            created += 1
            continue
        changed = [field for field, value in values.items() if getattr(item, field) != value]
        if changed:
            for field in changed:
                setattr(item, field, values[field])
            item.save(update_fields=changed)
            updated += 1
    return created, updated
