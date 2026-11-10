"""Immagini delle ricette (progettazione 4.6, ADR 0011).

Senza immagine la ricetta mostra il disegno della sua categoria. Una foto vera
si carica a mano e vince sempre; altrimenti, su richiesta, Gemini ne disegna
una. Tutto diventa WebP ridotto, senza EXIF.
"""

from __future__ import annotations

import io

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

from apps.ai.client import generate_image
from apps.ai.models import AiCall

from .models import Recipe

FEATURE = "recipe_image"

PROMPT = """Fotografia di cucina realistica e appetitosa del piatto "{title}".
{description}Ingredienti principali: {ingredients}.
Il piatto pronto in un piatto di ceramica su un tavolo di legno chiaro, vista
a 45 gradi, luce naturale morbida, sfondo sfocato. Niente testo, scritte,
loghi, persone o mani."""


class ImageRejected(ValueError):
    pass


def to_webp(data: bytes) -> bytes:
    """Immagine ruotata come nel telefono, ridotta, senza EXIF, in WebP."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((settings.RECIPE_IMAGE_MAX_SIDE, settings.RECIPE_IMAGE_MAX_SIDE))
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            out = io.BytesIO()
            image.save(out, "WEBP", quality=82, method=4)
            return out.getvalue()
    except Exception as exc:
        raise ImageRejected(_("Il file non si apre come immagine.")) from exc


def set_image(recipe: Recipe, data: bytes, source: str) -> None:
    old = recipe.image.name if recipe.image else ""
    recipe.image.save("image.webp", ContentFile(to_webp(data)), save=False)
    recipe.image_source = source
    recipe.save(update_fields=["image", "image_source", "updated_at"])
    if old:
        recipe.image.storage.delete(old)


def clear_image(recipe: Recipe) -> None:
    if recipe.image:
        recipe.image.delete(save=False)
    recipe.image = ""
    recipe.image_source = ""
    recipe.save(update_fields=["image", "image_source", "updated_at"])


def images_today(user) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return AiCall.objects.filter(user=user, feature=FEATURE, created_at__gte=start).count()


def image_prompt(recipe: Recipe) -> str:
    """Solo titolo, descrizione e ingredienti: niente del profilo."""
    names = [
        line.ingredient.display_name
        for line in recipe.ingredients.select_related("ingredient").order_by("position")
        if not line.optional and not line.ingredient.staple
    ]
    description = " ".join(recipe.description.split())[:300]
    return PROMPT.format(
        title=recipe.title,
        description=f"{description}\n" if description else "",
        ingredients=", ".join(names[:8]) or "a tua scelta, coerenti col titolo",
    )


def draw_image(recipe: Recipe, user) -> str:
    """Fa disegnare l'immagine a Gemini e la salva; restituisce il modello usato."""
    data, _mime, model = generate_image(image_prompt(recipe), feature=FEATURE, user=user)
    set_image(recipe, data, Recipe.ImageSource.AI)
    return model
