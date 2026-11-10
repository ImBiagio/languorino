from django.contrib import admin

from .models import Ingredient, Recipe, RecipeIngredient, Tag


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "name_en", "category", "default_unit", "staple", "created_by"]
    list_filter = ["category", "staple", ("created_by", admin.EmptyFieldListFilter)]
    search_fields = ["name", "name_en", "search_text"]
    readonly_fields = ["keys", "search_text"]


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    autocomplete_fields = ["ingredient"]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "difficulty", "servings", "in_cookbook", "updated_at"]
    list_filter = ["difficulty", "in_cookbook", "source", "status"]
    search_fields = ["title", "owner__email"]
    inlines = [RecipeIngredientInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "owner"]
    search_fields = ["name", "owner__email"]
