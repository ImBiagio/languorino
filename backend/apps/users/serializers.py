from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "handle",
            "avatar",
            "email_verified_at",
            "language",
        ]
        # Nome ed email si cambiano su cornhub (account unico della suite):
        # qui restano indirizzo pubblico, avatar e lingua.
        read_only_fields = ["id", "email", "display_name", "email_verified_at"]
        extra_kwargs = {"handle": {"required": False, "allow_null": True}}

    def validate_handle(self, value: str | None) -> str | None:
        from apps.community.profiles import validate_handle

        if not value:
            # Senza indirizzo il profilo pubblico non si apre: se ci sono
            # ricette pubbliche se ne crea uno nuovo alla prossima pubblicazione.
            return None
        return validate_handle(value, self.instance)


class UserBriefSerializer(serializers.ModelSerializer):
    """Usato ovunque si mostri chi ha creato o condiviso qualcosa."""

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "avatar"]
        read_only_fields = fields


class TokenPairSerializer(serializers.Serializer):
    """Solo l'access token esce nel body: il refresh vive in un cookie httpOnly."""

    access = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)
