from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.utils.translation import gettext as _
from pydantic import ValidationError as PydanticError
from rest_framework import serializers

from apps.profiles.models import MEAL_SLOT_ORDER, MealSlot
from apps.recipes.models import Difficulty, RecipeBook, Unit
from apps.recipes.serializers import RecipeListSerializer
from apps.shopping.aggregate import TO_BASE

from .models import MealPlan, NutritionistPlan, PlannedMeal, PrepMode
from .nutritionist import NutritionistRules, clean_rules

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
    nutritionist_plan = serializers.UUIDField(required=False, allow_null=True, default=None)
    # Quanti pasti con ricette nuove scritte dall'LLM, in percentuale; il resto
    # dalle fonti scelte (ricettario, ricettari PDF).
    new_share = serializers.ChoiceField(choices=(0, 25, 50, 75, 100), default=25)

    def validate_nutritionist_plan(self, value):
        if value is None:
            return None
        user = self.context["request"].user
        if not NutritionistPlan.objects.filter(
            owner=user, id=value, status=NutritionistPlan.Status.CONFIRMED
        ).exists():
            raise serializers.ValidationError(_("Piano del nutrizionista non trovato."))
        return str(value)

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
            "nutritionist_plan": data["nutritionist_plan"],
            "new_share": data["new_share"],
        }


class PlannedMealSerializer(serializers.ModelSerializer):
    recipe = RecipeListSerializer(read_only=True)
    recipe_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    portion = serializers.SerializerMethodField()

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
            "portion",
        ]
        read_only_fields = ["id", "date", "slot", "note", "portion"]

    def get_portion(self, meal: PlannedMeal) -> list[dict]:
        """Quanto mangia una persona di ogni ingrediente: la ricetta divisa per
        le sue porzioni. Senza "q.b." e facoltativi: servono le grammature."""
        recipe = meal.recipe
        if recipe is None:
            return []
        servings = Decimal(recipe.servings or 1)
        lines = []
        for line in recipe.ingredients.all():
            if line.optional or line.quantity is None or line.unit == Unit.TO_TASTE:
                continue
            quantity = line.quantity / servings
            item = {
                "name": line.ingredient.display_name,
                "quantity": str(round(quantity, 2)),
                "unit": line.unit,
            }
            # Pezzi, cucchiai, tazze: anche il peso, se il catalogo lo sa
            # ("zucchina ½ pz" dice poco a chi conta le grammature).
            grams_per_piece = line.ingredient.grams_per_piece
            if line.unit == Unit.PIECE and grams_per_piece:
                item["approx"] = {
                    "quantity": str(round(quantity * Decimal(grams_per_piece))),
                    "unit": Unit.GRAM.value,
                }
            elif line.unit in TO_BASE and line.unit not in (Unit.GRAM, Unit.MILLILITRE):
                base, factor = TO_BASE[line.unit]
                item["approx"] = {"quantity": str(round(quantity * factor)), "unit": base.value}
            lines.append(item)
        return lines

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
    nutritionist = serializers.SerializerMethodField()

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
            "nutritionist",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_nutritionist(self, plan: MealPlan) -> dict | None:
        chosen = plan.settings.get("nutritionist_plan")
        if not chosen:
            return None
        found = NutritionistPlan.objects.filter(owner=plan.owner, id=chosen).first()
        return {"id": str(found.id), "title": found.title} if found else None

    def get_end_date(self, plan: MealPlan) -> date:
        return plan.start_date + timedelta(days=plan.days - 1)


class MealPlanDetailSerializer(MealPlanSerializer):
    meals = PlannedMealSerializer(many=True, read_only=True)

    class Meta(MealPlanSerializer.Meta):
        fields = [*MealPlanSerializer.Meta.fields, "meals"]
        read_only_fields = fields


class NutritionistPlanSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()

    class Meta:
        model = NutritionistPlan
        fields = [
            "id",
            "title",
            "status",
            "strict",
            "valid_from",
            "valid_to",
            "rules",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "files", "created_at", "updated_at"]

    def get_files(self, plan: NutritionistPlan) -> list[dict]:
        if plan.job is None:
            return []
        return [
            {"original_name": item.original_name, "content_type": item.content_type}
            for item in plan.job.files.all()
        ]

    def validate_title(self, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("Dai un nome al piano."))
        return value

    def validate_rules(self, value):
        try:
            rules = NutritionistRules.model_validate(value)
        except PydanticError as exc:
            raise serializers.ValidationError(_("Regole non valide.")) from exc
        return clean_rules(rules)

    def validate(self, attrs):
        start = attrs.get("valid_from", getattr(self.instance, "valid_from", None))
        end = attrs.get("valid_to", getattr(self.instance, "valid_to", None))
        if start and end and end < start:
            raise serializers.ValidationError({"valid_to": _("La fine viene prima dell'inizio.")})
        return attrs
