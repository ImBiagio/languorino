from __future__ import annotations

from datetime import timedelta

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.recipes.models import Unit

from .models import RecurringItem, ShoppingItem, ShoppingList


class ShoppingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingItem
        fields = [
            "id",
            "label",
            "quantity",
            "unit",
            "category",
            "checked",
            "in_pantry",
            "manual",
            "edited",
            "sources",
        ]
        read_only_fields = ["id", "category", "manual", "edited", "sources"]

    def validate_label(self, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("Scrivi cosa comprare."))
        return value

    def validate_unit(self, value: str) -> str:
        if value and value not in Unit.values:
            raise serializers.ValidationError(_("Unità sconosciuta."))
        return value

    def validate_quantity(self, value):
        if value is not None and value <= 0:
            return None
        return value


class RecurringItemSerializer(serializers.ModelSerializer):
    """Un ricorrente: quantita' per volta (per tutta la casa) e volte a settimana."""

    class Meta:
        model = RecurringItem
        fields = ["id", "label", "quantity", "unit", "times_per_week", "slot", "active"]
        read_only_fields = ["id"]
        extra_kwargs = {"times_per_week": {"min_value": 1, "max_value": 21}}

    validate_label = ShoppingItemSerializer.validate_label
    validate_unit = ShoppingItemSerializer.validate_unit
    validate_quantity = ShoppingItemSerializer.validate_quantity

    def validate_slot(self, value: str) -> str:
        from apps.profiles.models import MEAL_SLOT_ORDER

        return value if value in MEAL_SLOT_ORDER else ""

    def validate(self, attrs):
        # "2 caffe'" senza unita': sono pezzi.
        unit = attrs.get("unit", self.instance.unit if self.instance else "")
        if attrs.get("quantity") is not None and not unit:
            attrs["unit"] = Unit.PIECE
        return attrs


class ShoppingListSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True, default=0)
    checked_count = serializers.IntegerField(read_only=True, default=0)
    # Di chi e' la lista, se non e' di chi chiede (ADR 0025): null = mia.
    shared_by = serializers.SerializerMethodField()

    def get_shared_by(self, obj) -> str | None:
        request = self.context.get("request")
        if request is None or obj.owner_id == request.user.id:
            return None
        return str(obj.owner)

    class Meta:
        model = ShoppingList
        fields = [
            "id",
            "title",
            "plan",
            "date_from",
            "date_to",
            "status",
            "include_recurring",
            "shared_by",
            "item_count",
            "checked_count",
            "created_at",
        ]
        read_only_fields = ["id", "plan", "date_from", "date_to", "created_at"]


class ShoppingListDetailSerializer(ShoppingListSerializer):
    items = ShoppingItemSerializer(many=True, read_only=True)

    class Meta(ShoppingListSerializer.Meta):
        fields = [*ShoppingListSerializer.Meta.fields, "items"]


class ShoppingListCreateSerializer(serializers.Serializer):
    """Dal piano (``plan`` e intervallo di giorni) o vuota (solo ``title``)."""

    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    plan = serializers.UUIDField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    include_recurring = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        from apps.plans.models import MealPlan

        plan_id = attrs.get("plan")
        if not plan_id:
            attrs["plan"] = None
            return attrs
        plan = MealPlan.objects.filter(id=plan_id, owner=self.context["request"].user).first()
        if plan is None:
            raise serializers.ValidationError({"plan": _("Piano non trovato.")})
        end = plan.start_date + timedelta(days=plan.days - 1)
        attrs["plan"] = plan
        attrs["date_from"] = max(attrs.get("date_from") or plan.start_date, plan.start_date)
        attrs["date_to"] = min(attrs.get("date_to") or end, end)
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_to": _("L'intervallo di giorni è vuoto.")})
        return attrs
