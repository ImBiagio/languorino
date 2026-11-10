"""Ricettario: ingredienti (catalogo condiviso), ricette dell'utente, tag.

Le ricette sono pensate per il meal prep (progettazione, sezione 3): porzioni,
tempi, difficolta', per quali pasti vanno bene e quanti giorni si conservano.
Gli allergeni di una ricetta non si scrivono: si ricavano dagli ingredienti.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.profiles.allergens import Allergen
from apps.profiles.models import MealSlot

from .matching import keys_for


class Category(models.TextChoices):
    """Reparti, in ordine di giro al supermercato: ordinano la lista della spesa."""

    PRODUCE = "produce", _("Frutta e verdura")
    MEAT = "meat", _("Carne e salumi")
    FISH = "fish", _("Pesce")
    DAIRY = "dairy", _("Latticini e uova")
    BAKERY = "bakery", _("Pane e forno")
    PANTRY = "pantry", _("Dispensa")
    SPICES = "spices", _("Spezie e condimenti")
    FROZEN = "frozen", _("Surgelati")
    DRINKS = "drinks", _("Bevande")
    OTHER = "other", _("Altro")


class Unit(models.TextChoices):
    GRAM = "g", "g"
    KILO = "kg", "kg"
    MILLILITRE = "ml", "ml"
    LITRE = "l", "l"
    PIECE = "pz", _("pz")
    TABLESPOON = "tbsp", _("cucchiaio")
    TEASPOON = "tsp", _("cucchiaino")
    CUP = "cup", _("tazza")
    PINCH = "pinch", _("pizzico")
    CLOVE = "clove", _("spicchio")
    SLICE = "slice", _("fetta")
    BUNCH = "bunch", _("mazzetto")
    CAN = "can", _("scatola")
    TO_TASTE = "to_taste", _("q.b.")


class Difficulty(models.TextChoices):
    EASY = "easy", _("Facile")
    MEDIUM = "medium", _("Media")
    HARD = "hard", _("Difficile")


class Ingredient(BaseModel):
    """Un ingrediente del catalogo (``created_by`` vuoto) o aggiunto da un utente."""

    name = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80, blank=True)
    # Nome, nome inglese e sinonimi normalizzati (matching.normalize): il
    # riconoscimento esatto passa da qui, la ricerca per pezzi da search_text.
    keys = ArrayField(models.CharField(max_length=80), default=list, blank=True)
    search_text = models.TextField(blank=True, editable=False)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.OTHER)
    allergens = ArrayField(
        models.CharField(max_length=12, choices=Allergen.choices), default=list, blank=True
    )
    default_unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.GRAM)
    # Per passare da "2 uova" ai grammi quando si somma la spesa.
    grams_per_piece = models.PositiveIntegerField(null=True, blank=True)
    # Quanti giorni dura fresco: il piano mettera' prima quello che dura meno.
    perishable_days = models.PositiveSmallIntegerField(null=True, blank=True)
    # Sale, olio, pepe: nella spesa partono come "ce l'ho gia'".
    staple = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ingredients",
    )

    class Meta:
        ordering = ["name"]
        indexes = [GinIndex(fields=["keys"], name="ingredient_keys_gin")]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                condition=Q(created_by__isnull=True),
                name="unique_catalog_ingredient",
            ),
            models.UniqueConstraint(
                Lower("name"),
                "created_by",
                condition=Q(created_by__isnull=False),
                name="unique_user_ingredient",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def set_keys(self, aliases: list[str] | tuple[str, ...] = ()) -> None:
        self.keys = keys_for(self.name, self.name_en, *aliases)
        self.search_text = " | ".join(self.keys)

    @property
    def display_name(self) -> str:
        """Il nome nella lingua attiva: l'inglese se c'e', altrimenti l'italiano."""
        if (get_language() or "it").startswith("en") and self.name_en:
            return self.name_en
        return self.name


class Tag(BaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_tags"
    )
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ["name"]
        constraints = [
            # I tag si cancellano davvero: il vincolo vale su tutte le righe.
            models.UniqueConstraint("owner", Lower("name"), name="unique_tag_per_owner"),
        ]

    def __str__(self) -> str:
        return self.name


class Recipe(BaseModel):
    class Source(models.TextChoices):
        MANUAL = "manual", _("Scritta a mano")
        PHOTO = "photo", _("Da foto")
        PDF = "pdf", _("Da PDF")
        VOICE = "voice", _("A voce")
        PLAN = "plan", _("Dal piano")
        FRIDGE = "fridge", _("Dal frigo")
        COPY = "copy", _("Copiata")

    class Status(models.TextChoices):
        # Le ricette importate o scritte dall'LLM nascono bozza (progettazione,
        # principio 1); quelle scritte a mano sono subito confermate.
        DRAFT = "draft", _("Bozza")
        CONFIRMED = "confirmed", _("Confermata")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=2000)
    servings = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    prep_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(1440)])
    cook_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(1440)])
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices, default=Difficulty.EASY)
    # Passi in ordine: testo e basta, non servono query sui singoli passi.
    steps = models.JSONField(default=list, blank=True)
    meal_slots = ArrayField(
        models.CharField(max_length=16, choices=MealSlot.choices), default=list, blank=True
    )
    # Quanti giorni regge in frigo una volta cucinata: decide se va bene per il
    # prep (vuoto = non lo so).
    keeps_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10)]
    )
    freezable = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="recipes")
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.MANUAL)
    # Falso per le ricette scritte dall'LLM nel piano e non ancora salvate.
    in_cookbook = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def total_minutes(self) -> int:
        return self.prep_minutes + self.cook_minutes


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    # PROTECT: un ingrediente usato da una ricetta non sparisce dal catalogo.
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="uses")
    # Vuota per "q.b." o quando la ricetta non lo dice.
    quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.GRAM)
    note = models.CharField(max_length=80, blank=True)
    optional = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"{self.quantity or ''} {self.unit} {self.ingredient}".strip()
