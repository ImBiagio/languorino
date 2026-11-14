from django.db import migrations


def forwards(apps, schema_editor):
    # Le ricette gia' condivise con il link restano visibili a chi ha il link.
    Recipe = apps.get_model("recipes", "Recipe")
    Recipe.objects.filter(share_token__isnull=False).update(visibility="unlisted")


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0009_recipe_visibility"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
