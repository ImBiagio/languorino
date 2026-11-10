from __future__ import annotations

from datetime import date, timedelta

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.profiles.models import MEAL_SLOT_ORDER, MealSlot
from apps.recipes.models import Difficulty, RecipeBook
from apps.recipes.serializers import RecipeListSerializer

from .models import MealPlan, PlannedMeal, PrepMode

ALLOWED_DAYS = (7, 14, 21, 28)


class PlanSettingsSerializer(serializers.Serializer):
    """Le scelte della procedura "Nuovo piano"."""

    start_date = serializers.DateField()
    days = serializers.ChoiceField(choices=ALLOWED_DAYS)
    slots = serializers.ListField(child=serializers.ChoiceField(choices=MealSlot.choices))
    servings = serializers.IntegerField(min_value=1, max_value=12)
    prep_mode = serializers.ChoiceField(choices=PrepMode.choices, default=PrepMode.NONE)
    minutes = serializers.IntegerField(min_value=10, max_value=300, default=45)
    difficulty = serializers.ChoiceField(choices=Difficulty.choices, default=Difficulty.MEDIUM)
    use_cookbook = serializers.BooleanField(default=True)
    books = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    include_tags = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, default=list, max_length=12
    )
    exclude_tags = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, default=list, max_length=12
    )
    goal_note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_start_date(self, value: date) -> date:
        today = date.today()
        if not today - timedelta(days=1) <= value <= today + timedelta(days=60):
            raise serializers.ValidationError(_("Scegli un giorno tra oggi e i prossimi due mesi."))
        return value

    def validate_slots(self, value: list[str]) -> list[str]:
        if not value:
            raise serializers.ValidationError(_("Scegli almeno un pasto."))
        return sorted(set(value), key=MEAL_SLOT_ORDER.index)

    def validate_books(self, value):
        user = self.context["request"].user
        owned = set(
            RecipeBook.objects.filter(owner=user, id__in=value).values_list("id", flat=True)
        )
        if len(owned) != len(set(value)):
            raise serializers.ValidationError(_("Ricettario non trovato."))
        return [str(book) for book in value]

    def validate(self, attrs):
        if not attrs["use_cookbook"] and not attrs["books"]:
            raise serializers.ValidationError(
                {"books": _("Scegli almeno una fonte: il tuo ricettario o un ricettario PDF.")}
            )
        for key in ("include_tags", "exclude_tags"):
            attrs[key] = list(
                dict.fromkeys(" ".join(tag.split()) for tag in attrs[key] if tag.strip())
            )
        return attrs

    def to_settings(self) -> dict:
        data = self.validated_data
        return {
            "slots": data["slots"],
            "servings": data["servings"],
            "prep_mode": data["prep_mode"],
            "minutes": data["minutes"],
            "difficulty": data["difficulty"],
            "sources": {"cookbook": data["use_cookbook"], "books": data["books"]},
            "include_tags": data["include_tags"],
            "exclude_tags": data["exclude_tags"],
            "goal_note": data["goal_note"].strip(),
        }


class PlannedMealSerializer(serializers.ModelSerializer):
    recipe = RecipeListSerializer(read_only=True)
    recipe_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PlannedMeal
        fields = [
            "id",
            "date",
            "slot",
            "recipe",
            "recipe_id",
            "servings",
            "cooked_on",
            "note",
            "eaten",
        ]
        read_only_fields = ["id", "date", "slot", "note"]

    def validate_servings(self, value: int) -> int:
        if not 1 <= value <= 50:
            raise serializers.ValidationError(_("Da 1 a 50 porzioni."))
        return value

    def validate(self, attrs):
        meal: PlannedMeal = self.instance
        if "cooked_on" in attrs and attrs["cooked_on"] > meal.date:
            raise serializers.ValidationError(
                {"cooked_on": _("Non si può cucinare dopo averlo mangiato.")}
            )
        return attrs


class MealPlanSerializer(serializers.ModelSerializer):
    weeks_total = serializers.IntegerField(read_only=True)
    end_date = serializers.SerializerMethodField()

    class Meta:
        model = MealPlan
        fields = [
            "id",
            "start_date",
            "end_date",
            "days",
            "status",
            "settings",
            "weeks_done",
            "weeks_total",
            "error",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_end_date(self, plan: MealPlan) -> date:
        return plan.start_date + timedelta(days=plan.days - 1)


class MealPlanDetailSerializer(MealPlanSerializer):
    meals = PlannedMealSerializer(many=True, read_only=True)

    class Meta(MealPlanSerializer.Meta):
        fields = [*MealPlanSerializer.Meta.fields, "meals"]
        read_only_fields = fields
