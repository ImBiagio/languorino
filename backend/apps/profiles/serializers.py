from __future__ import annotations

from datetime import date

from django.utils.translation import gettext as _
from rest_framework import serializers

from .allergens import detect_allergen
from .models import MEAL_SLOT_ORDER, FoodPreference, Profile

MAX_CONDITIONS = 20


def _dedupe(values: list[str]) -> list[str]:
    """Toglie doppioni e voci vuote tenendo l'ordine (senza badare alle maiuscole)."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = " ".join(value.split())
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)
    return out


class FoodPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodPreference
        fields = ["id", "kind", "label", "allergen"]
        read_only_fields = ["id"]
        # L'unicita' (stessa etichetta due volte) la gestisce la view: rimandare
        # quella che c'e' gia' e' piu' utile di un 400.
        validators: list = []

    def validate_label(self, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("Scrivi qualcosa."))
        return value

    def validate(self, attrs):
        kind = attrs.get("kind")
        restriction = kind in {FoodPreference.Kind.ALLERGY, FoodPreference.Kind.INTOLERANCE}
        if not restriction:
            # Su gusti e antipatie l'allergene non vuol dire niente.
            attrs["allergen"] = ""
        elif not attrs.get("allergen"):
            attrs["allergen"] = detect_allergen(attrs["label"])
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)
    onboarding_completed = serializers.SerializerMethodField()
    preferences = FoodPreferenceSerializer(many=True, read_only=True)
    # Voci vuote ammesse in ingresso: le toglie validate_conditions, invece di
    # rifiutare tutta la lista per una riga lasciata vuota.
    conditions = serializers.ListField(
        child=serializers.CharField(allow_blank=True, max_length=120), required=False
    )

    class Meta:
        model = Profile
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "age",
            "sex",
            "height_cm",
            "weight_kg",
            "goals",
            "goals_note",
            "activity_level",
            "sport_sessions_per_week",
            "conditions",
            "followed_by_nutritionist",
            "meal_slots",
            "household_size",
            "onboarding_completed",
            "preferences",
        ]

    def get_onboarding_completed(self, profile: Profile) -> bool:
        return profile.onboarding_completed_at is not None

    def validate_first_name(self, value: str) -> str:
        return " ".join(value.split())

    def validate_last_name(self, value: str) -> str:
        return " ".join(value.split())

    def validate_birth_date(self, value: date | None) -> date | None:
        if value is None:
            return value
        if value > date.today():
            raise serializers.ValidationError(_("La data di nascita non può essere nel futuro."))
        if value.year < 1900:
            raise serializers.ValidationError(_("Controlla l'anno di nascita."))
        return value

    def validate_goals(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    def validate_conditions(self, value: list[str]) -> list[str]:
        value = _dedupe(value)
        if len(value) > MAX_CONDITIONS:
            raise serializers.ValidationError(_("Al massimo %(n)d voci.") % {"n": MAX_CONDITIONS})
        return value

    def validate_meal_slots(self, value: list[str]) -> list[str]:
        if not value:
            raise serializers.ValidationError(_("Scegli almeno un pasto."))
        # Sempre in ordine di giornata, qualunque sia l'ordine dei tocchi.
        return sorted(set(value), key=MEAL_SLOT_ORDER.index)

    def update(self, instance: Profile, validated_data):
        profile = super().update(instance, validated_data)
        user = profile.user
        # Alla registrazione il nome visibile e' la parte prima della @: appena
        # si dice come ci si chiama, quello vero lo sostituisce. Uno scelto a
        # mano non si tocca.
        if profile.first_name and user.display_name == user.email.split("@")[0]:
            user.display_name = profile.first_name
            user.save(update_fields=["display_name"])
        return profile
