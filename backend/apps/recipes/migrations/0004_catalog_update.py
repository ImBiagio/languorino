"""Catalogo aggiornato: sinonimi nuovi (albume d'uovo, farina d'avena)."""

from django.db import migrations


def load(apps, schema_editor):
    from apps.recipes.catalog_loader import load_catalog

    load_catalog(apps.get_model("recipes", "Ingredient"))


class Migration(migrations.Migration):
    dependencies = [("recipes", "0003_recipebook_recipe_book")]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
