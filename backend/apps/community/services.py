"""Voti e commenti: regole che valgono per l'API e per i test."""

from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Avg, Count
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.jobs.files import sniff
from apps.recipes.images import ImageRejected, to_webp
from apps.recipes.models import Recipe

from .models import Comment, CommentImage, Rating

MAX_IMAGES = 3
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def rating_summary(recipe: Recipe, user=None) -> dict:
    """Media, numero di voti e il voto di chi guarda."""
    stats = Rating.objects.filter(recipe=recipe).aggregate(avg=Avg("stars"), count=Count("id"))
    mine = None
    if user is not None and getattr(user, "is_authenticated", False):
        mine = (
            Rating.objects.filter(recipe=recipe, user=user).values_list("stars", flat=True).first()
        )
    return {
        "average": round(float(stats["avg"]), 1) if stats["avg"] is not None else None,
        "count": stats["count"],
        "mine": mine,
    }


def rate(recipe: Recipe, user, stars: int) -> Rating:
    if recipe.owner_id == user.id:
        raise serializers.ValidationError({"stars": _("Non puoi votare una tua ricetta.")})
    if not 1 <= stars <= 5:
        raise serializers.ValidationError({"stars": _("Da 1 a 5 stelle.")})
    rating, _created = Rating.objects.update_or_create(
        recipe=recipe, user=user, defaults={"stars": stars}
    )
    return rating


def _read_images(uploads) -> list[bytes]:
    if len(uploads) > MAX_IMAGES:
        raise serializers.ValidationError(
            {"images": _("Al massimo %(n)d foto per commento.") % {"n": MAX_IMAGES}}
        )
    images = []
    for upload in uploads:
        data = upload.read()
        if sniff(data[:16]) not in PHOTO_TYPES:
            raise serializers.ValidationError({"images": _("Servono foto JPEG, PNG o WebP.")})
        if len(data) > settings.JOB_MAX_IMAGE_BYTES:
            raise serializers.ValidationError(
                {
                    "images": _("Foto troppo grande (massimo %(mb)d MB).")
                    % {"mb": settings.JOB_MAX_IMAGE_BYTES // (1024 * 1024)}
                }
            )
        try:
            images.append(to_webp(data))
        except ImageRejected as exc:
            raise serializers.ValidationError({"images": str(exc)}) from exc
    return images


@transaction.atomic
def add_comment(recipe: Recipe, user, text: str, *, parent_id=None, uploads=()) -> Comment:
    text = (text or "").strip()
    images = _read_images(list(uploads))
    if not text and not images:
        raise serializers.ValidationError({"text": _("Scrivi qualcosa o aggiungi una foto.")})
    if len(text) > 2000:
        raise serializers.ValidationError({"text": _("Al massimo 2000 caratteri.")})
    parent = None
    if parent_id:
        parent = Comment.objects.filter(recipe=recipe, pk=parent_id).first()
        if parent is None:
            raise serializers.ValidationError({"parent": _("Commento non trovato.")})
        # Un solo livello di risposte: si risponde al filo.
        parent = parent.parent or parent
    comment = Comment.objects.create(recipe=recipe, author=user, parent=parent, text=text)
    for position, data in enumerate(images):
        item = CommentImage(comment=comment, position=position)
        item.image.save("image.webp", ContentFile(data), save=False)
        item.save()
    return comment


def can_delete(comment: Comment, user) -> bool:
    """L'autore del commento e l'autore della ricetta (che modera la sua pagina)."""
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.id in (comment.author_id, comment.recipe.owner_id)
    )


@transaction.atomic
def delete_comment(comment: Comment) -> None:
    """Via il testo e le foto subito; il commento resta come "eliminato" solo
    se tiene in piedi delle risposte."""
    for item in comment.images.all():
        item.delete()
    comment.text = ""
    comment.save(update_fields=["text", "updated_at"])
    comment.delete()
