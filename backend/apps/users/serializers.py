from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.methods import normalize_email

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
        read_only_fields = ["id", "email", "email_verified_at"]
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


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    display_name = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value: str) -> str:
        value = normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("Esiste gia' un account con questa email."))
        return value

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            display_name=validated_data.get("display_name", ""),
            # La lingua in cui si sta registrando: anche la mail di conferma.
            language=translation.get_language() or settings.LANGUAGE_CODE,
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value, self.context["request"].user)
        return value


class TokenPairSerializer(serializers.Serializer):
    """Solo l'access token esce nel body: il refresh vive in un cookie httpOnly."""

    access = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)


class EmailSerializer(serializers.Serializer):
    """Reinvio della conferma e richiesta di reset: basta l'indirizzo."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
