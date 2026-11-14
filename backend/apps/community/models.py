"""Le ricette condivise viste dagli altri (ADR 0017): voti da 1 a 5 stelle,
commenti con risposte e foto. Si arriva a una ricetta solo dal suo link
(``share_token``): una ricetta privata non si vota e non si commenta."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.models import BaseModel
from apps.recipes.models import Recipe


class Rating(models.Model):
    """Il voto di un utente a una ricetta: uno solo, si cambia o si toglie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_ratings"
    )
    stars = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint("recipe", "user", name="one_rating_per_user"),
            models.CheckConstraint(
                condition=models.Q(stars__gte=1, stars__lte=5), name="rating_stars_1_5"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipe} {self.stars}★"


class Comment(BaseModel):
    """Un commento o una risposta. Le risposte stanno su un solo livello:
    rispondere a una risposta la attacca al commento da cui parte il filo."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    text = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.text[:40]


def comment_image_path(instance: CommentImage, filename: str) -> str:
    from apps.core.methods import random_token

    return f"comments/{instance.comment.recipe_id}/{instance.comment_id}-{random_token(6)}.webp"


class CommentImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="images")
    # WebP ridotto e senza EXIF come le foto delle ricette.
    image = models.ImageField(upload_to=comment_image_path, max_length=200)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return self.image.name


@receiver(post_delete, sender=CommentImage)
def _delete_file(sender, instance: CommentImage, **kwargs) -> None:
    if instance.image:
        instance.image.delete(save=False)
