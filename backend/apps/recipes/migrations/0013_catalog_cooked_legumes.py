"""Catalogo aggiornato: legumi lessati come quelli in scatola (ADR 0023)."""

from django.db import migrations


def load(apps, schema_editor):
    from apps.recipes.catalog_loader import load_catalog

    load_catalog(apps.get_model("recipes", "Ingredient"))


class Migration(migrations.Migration):
    dependencies = [("recipes", "0012_recipebook_reread")]

    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
