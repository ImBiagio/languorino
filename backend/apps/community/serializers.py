from __future__ import annotations

from rest_framework import serializers

from .models import Comment
from .services import can_delete


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    stars = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    is_deleted = serializers.BooleanField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "text",
            "images",
            "stars",
            "created_at",
            "can_delete",
            "is_deleted",
            "replies",
        ]
        read_only_fields = fields

    def get_author(self, comment: Comment) -> dict | None:
        if comment.is_deleted:
            return None
        handles = self.context.get("public_handles", {})
        return {
            "name": comment.author.display_name,
            # Il link al profilo solo se il profilo e' pubblico.
            "handle": handles.get(comment.author_id),
            "is_recipe_author": comment.author_id == comment.recipe.owner_id,
        }

    def get_images(self, comment: Comment) -> list[str]:
        if comment.is_deleted:
            return []
        return [item.image.url for item in comment.images.all()]

    def get_stars(self, comment: Comment) -> int | None:
        """Il voto che l'autore del commento ha dato alla ricetta."""
        if comment.is_deleted:
            return None
        return self.context.get("stars", {}).get(comment.author_id)

    def get_can_delete(self, comment: Comment) -> bool:
        request = self.context.get("request")
        return not comment.is_deleted and can_delete(comment, getattr(request, "user", None))

    def get_replies(self, comment: Comment) -> list[dict]:
        replies = self.context.get("replies", {}).get(comment.id, [])
        return CommentSerializer(replies, many=True, context=self.context).data
