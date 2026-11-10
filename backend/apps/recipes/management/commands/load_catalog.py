from django.core.management.base import BaseCommand

from apps.recipes.catalog_loader import load_catalog
from apps.recipes.models import Ingredient


class Command(BaseCommand):
    help = "Carica o aggiorna il catalogo degli ingredienti da apps/recipes/catalog.py."

    def handle(self, *args, **options):
        created, updated = load_catalog(Ingredient)
        self.stdout.write(f"Catalogo: {created} creati, {updated} aggiornati.")
