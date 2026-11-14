from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.profiles.models import MEAL_SLOT_ORDER

from .models import Category, Ingredient, Recipe, RecipeBook, RecipeIngredient, Tag, Unit
from .services import (
    PreferenceIndex,
    recipe_allergens,
    resolve_ingredient,
    visible_ingredients,
)

MAX_STEPS = 40
MAX_INGREDIENTS = 60
MAX_TAGS = 12


class IngredientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    custom = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = [
            "id",
            "name",
            "category",
            "allergens",
            "default_unit",
            "grams_per_piece",
            "staple",
            "custom",
        ]
        read_only_fields = fields

    def get_custom(self, ingredient: Ingredient) -> bool:
        """Aggiunto dall'utente, non dal catalogo: reparto e allergeni non curati."""
        return ingredient.created_by_id is not None


class RecipeIngredientSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ["id", "ingredient", "quantity", "unit", "note", "optional"]


class RecipeIngredientWriteSerializer(serializers.Serializer):
    """Una riga del form: l'ingrediente scelto dai suggerimenti o scritto a mano."""

    ingredient_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    quantity = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0")
    )
    unit = serializers.ChoiceField(choices=Unit.choices, default=Unit.GRAM)
    note = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    optional = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("ingredient_id") and not (attrs.get("name") or "").strip():
            raise serializers.ValidationError(_("Scegli o scrivi un ingrediente."))
        # In un PATCH (partial) i default dei campi annidati non si applicano.
        attrs.setdefault("unit", Unit.GRAM)
        attrs.setdefault("optional", False)
        if attrs.get("quantity") == 0:
            attrs["quantity"] = None
        if attrs["unit"] == Unit.TO_TASTE:
            attrs["quantity"] = None
        attrs["note"] = " ".join(attrs.get("note", "").split())
        return attrs


def _warnings_context(serializer) -> PreferenceIndex:
    """Un solo indice delle preferenze per tutta la risposta (anche per le liste)."""
    context = serializer.context
    if "preference_index" not in context:
        request = context.get("request")
        context["preference_index"] = PreferenceIndex(getattr(request, "user", None))
    return context["preference_index"]


class RecipeListSerializer(serializers.ModelSerializer):
    """Quello che serve a una card del ricettario."""

    tags = serializers.SerializerMethodField()
    total_minutes = serializers.IntegerField(read_only=True)
    allergens = serializers.SerializerMethodField()
    warnings = serializers.SerializerMethodField()
    main_category = serializers.SerializerMethodField()
    ingredient_count = serializers.SerializerMethodField()
    book = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "title",
            "image",
            "image_source",
            "servings",
            "total_minutes",
            "difficulty",
            "meal_slots",
            "tags",
            "allergens",
            "warnings",
            "main_category",
            "ingredient_count",
            "in_cookbook",
            "status",
            "book",
            "updated_at",
        ]
        read_only_fields = fields

    def get_book(self, recipe: Recipe) -> dict | None:
        """Il ricettario PDF da cui viene la ricetta, se viene da li'."""
        if recipe.book_id is None or recipe.book is None:
            return None
        return {"id": str(recipe.book_id), "title": recipe.book.title}

    def get_image(self, recipe: Recipe) -> str | None:
        """URL relativo (``/media/...``): il frontend lo mette sotto l'API."""
        return recipe.image.url if recipe.image else None

    def get_tags(self, recipe: Recipe) -> list[str]:
        return sorted((tag.name for tag in recipe.tags.all()), key=str.lower)

    def get_allergens(self, recipe: Recipe) -> list[str]:
        return recipe_allergens(recipe)

    def get_warnings(self, recipe: Recipe) -> list[dict]:
        return _warnings_context(self).warnings(recipe, recipe_allergens(recipe))

    def get_ingredient_count(self, recipe: Recipe) -> int:
        return len(recipe.ingredients.all())

    def get_main_category(self, recipe: Recipe) -> str:
        """Il reparto dell'ingrediente che pesa di piu' (esclusi i basilari):
        sceglie il disegno della card quando non c'e' una foto."""
        best, weight = Category.OTHER.value, Decimal("-1")
        for line in recipe.ingredients.all():
            if line.ingredient.staple or line.optional:
                continue
            grams = line.quantity or Decimal("0")
            if line.unit == Unit.PIECE and line.ingredient.grams_per_piece:
                grams *= line.ingredient.grams_per_piece
            elif line.unit in (Unit.KILO, Unit.LITRE):
                grams *= 1000
            if grams > weight:
                best, weight = line.ingredient.category, grams
        return best


class RecipeSerializer(RecipeListSerializer):
    # In scrittura nomi e righe del form; in lettura li riscrive to_representation.
    tags = serializers.ListField(
        child=serializers.CharField(max_length=40, allow_blank=True),
        required=False,
        max_length=MAX_TAGS,
        write_only=True,
    )
    steps = serializers.ListField(
        child=serializers.CharField(max_length=2000, allow_blank=True),
        required=False,
        max_length=MAX_STEPS,
    )
    ingredients = RecipeIngredientWriteSerializer(
        many=True, required=False, max_length=MAX_INGREDIENTS, write_only=True
    )

    class Meta(RecipeListSerializer.Meta):
        fields = [
            *RecipeListSerializer.Meta.fields,
            "description",
            "prep_minutes",
            "cook_minutes",
            "steps",
            "keeps_days",
            "freezable",
            "ingredients",
            "source",
            "share_token",
            "copied_from",
            "kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "nutrition_source",
            "nutrition_detail",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "nutrition_detail",
            "share_token",
            "copied_from",
            "image",
            "image_source",
            "total_minutes",
            "allergens",
            "warnings",
            "main_category",
            "ingredient_count",
            "in_cookbook",
            "book",
            "source",
            "status",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, recipe: Recipe):
        data = super().to_representation(recipe)
        data["tags"] = sorted((tag.name for tag in recipe.tags.all()), key=str.lower)
        data["ingredients"] = RecipeIngredientSerializer(
            recipe.ingredients.all(), many=True, context=self.context
        ).data
        return data

    def validate_title(self, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("Dai un nome alla ricetta."))
        return value

    def validate_steps(self, value: list[str]) -> list[str]:
        # Le righe vuote del form si tolgono invece di rifiutare tutto.
        return [step.strip() for step in value if step.strip()]

    def validate_tags(self, value: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for raw in value:
            name = " ".join(raw.split())
            if name and name.lower() not in seen:
                seen[name.lower()] = name
        return list(seen.values())

    def validate_meal_slots(self, value: list[str]) -> list[str]:
        return sorted(set(value), key=MEAL_SLOT_ORDER.index)

    def validate_nutrition_source(self, value: str) -> str:
        # "ai" lo scrive solo la stima; il form puo' solo rimandarlo uguale.
        current = self.instance.nutrition_source if self.instance else ""
        if value == Recipe.NutritionSource.AI and current != value:
            raise serializers.ValidationError(_("Fonte non valida."))
        return value

    def _settle_nutrition(self, recipe: Recipe, validated_data, old_values, old_signature):
        """Chi ha scritto i valori (ADR 0018): cambiati a mano diventano
        "scritti a mano"; una stima dell'AI con ingredienti o porzioni
        cambiati non vale piu' e si toglie."""
        from .nutrition import FIELDS, clear, ingredients_signature

        values = {field: getattr(recipe, field) for field in FIELDS}
        changed = values != old_values
        if all(value is None for value in values.values()):
            clear(recipe)
        elif changed and validated_data.get("nutrition_source") in (None, "", "ai"):
            recipe.nutrition_source = Recipe.NutritionSource.MANUAL
            recipe.nutrition_detail = {}
        elif (
            not changed
            and recipe.nutrition_source == Recipe.NutritionSource.AI
            and old_signature is not None
            and ingredients_signature(recipe) != old_signature
        ):
            clear(recipe)
        if recipe.nutrition_source != Recipe.NutritionSource.AI:
            recipe.nutrition_detail = {}

    def _save_relations(self, recipe: Recipe, tags, ingredients) -> None:
        owner = recipe.owner
        if tags is not None:
            objs = []
            for name in tags:
                tag = Tag.objects.filter(owner=owner, name__iexact=name).first()
                objs.append(tag or Tag.objects.create(owner=owner, name=name))
            recipe.tags.set(objs)
        if ingredients is not None:
            recipe.ingredients.all().delete()
            lines = []
            for position, row in enumerate(ingredients):
                if row.get("ingredient_id"):
                    # Solo catalogo e ingredienti propri: non quelli di altri utenti.
                    ingredient = visible_ingredients(owner).filter(id=row["ingredient_id"]).first()
                    if ingredient is None:
                        raise serializers.ValidationError(
                            {"ingredients": _("Ingrediente non trovato.")}
                        )
                else:
                    ingredient = resolve_ingredient(row["name"], owner)
                lines.append(
                    RecipeIngredient(
                        recipe=recipe,
                        ingredient=ingredient,
                        quantity=row.get("quantity"),
                        unit=row["unit"],
                        note=row.get("note", ""),
                        optional=row.get("optional", False),
                        position=position,
                    )
                )
            RecipeIngredient.objects.bulk_create(lines)

    @transaction.atomic
    def create(self, validated_data):
        from .nutrition import FIELDS

        tags = validated_data.pop("tags", [])
        ingredients = validated_data.pop("ingredients", [])
        recipe = Recipe.objects.create(**validated_data)
        self._save_relations(recipe, tags, ingredients)
        self._settle_nutrition(recipe, validated_data, dict.fromkeys(FIELDS), None)
        recipe.save()
        return recipe

    @transaction.atomic
    def update(self, recipe: Recipe, validated_data):
        from .nutrition import FIELDS, ingredients_signature

        old_values = {field: getattr(recipe, field) for field in FIELDS}
        old_signature = (
            ingredients_signature(recipe)
            if recipe.nutrition_source == Recipe.NutritionSource.AI
            else None
        )
        tags = validated_data.pop("tags", None)
        ingredients = validated_data.pop("ingredients", None)
        recipe = super().update(recipe, validated_data)
        self._save_relations(recipe, tags, ingredients)
        # Le righe appena salvate, non quelle prefetchate prima.
        if hasattr(recipe, "_prefetched_objects_cache"):
            recipe._prefetched_objects_cache.pop("ingredients", None)
        self._settle_nutrition(recipe, validated_data, old_values, old_signature)
        recipe.save()
        return recipe


class TagSerializer(serializers.ModelSerializer):
    recipe_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "recipe_count"]
        read_only_fields = ["id", "recipe_count"]


class RecipeBookSerializer(serializers.ModelSerializer):
    recipe_count = serializers.IntegerField(read_only=True, default=0)
    saved_count = serializers.IntegerField(read_only=True, default=0)
    without_image = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = RecipeBook
        fields = [
            "id",
            "title",
            "original_name",
            "size",
            "page_count",
            "pages_done",
            "status",
            "error",
            "recipe_count",
            "saved_count",
            "without_image",
            "images_status",
            "images_pages_done",
            "images_found",
            "images_error",
            "created_at",
            "finished_at",
        ]
        read_only_fields = [field for field in fields if field != "title"]

    def validate_title(self, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("Dai un nome al ricettario."))
        return value


class SharedRecipeSerializer(RecipeListSerializer):
    """La ricetta per la pagina pubblica: niente avvisi dal profilo dell'autore,
    niente dati suoi oltre al nome che ha scelto di mostrare."""

    ingredients = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta(RecipeListSerializer.Meta):
        fields = [
            "id",
            "title",
            "image",
            "description",
            "servings",
            "prep_minutes",
            "cook_minutes",
            "total_minutes",
            "difficulty",
            "meal_slots",
            "keeps_days",
            "freezable",
            "steps",
            "tags",
            "allergens",
            "main_category",
            "ingredients",
            "kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "nutrition_source",
            "author",
            "is_mine",
        ]
        read_only_fields = fields

    def get_ingredients(self, recipe: Recipe) -> list[dict]:
        return RecipeIngredientSerializer(
            recipe.ingredients.all(), many=True, context=self.context
        ).data

    def get_author(self, recipe: Recipe) -> str:
        return recipe.owner.display_name

    def get_is_mine(self, recipe: Recipe) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and request.user == recipe.owner)
