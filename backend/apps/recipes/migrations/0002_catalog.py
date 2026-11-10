"""Carica il catalogo iniziale degli ingredienti (apps/recipes/catalog.py)."""

from django.db import migrations


def load(apps, schema_editor):
    from apps.recipes.catalog_loader import load_catalog

    load_catalog(apps.get_model("recipes", "Ingredient"))


class Migration(migrations.Migration):
    dependencies = [("recipes", "0001_initial")]

    # All'indietro non si toglie niente: le ricette potrebbero usarli.
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
