from django.contrib import admin

from .models import MealPlan, NutritionistPlan, PlannedMeal


class PlannedMealInline(admin.TabularInline):
    model = PlannedMeal
    extra = 0
    raw_id_fields = ["recipe"]


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ["start_date", "days", "status", "owner", "weeks_done"]
    list_filter = ["status"]
    search_fields = ["owner__email"]
    inlines = [PlannedMealInline]


@admin.register(NutritionistPlan)
class NutritionistPlanAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "strict", "valid_from", "valid_to", "created_at"]
    list_filter = ["status", "strict"]
    raw_id_fields = ["owner", "job"]
