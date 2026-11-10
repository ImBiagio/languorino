from django.contrib import admin

from .models import MealPlan, PlannedMeal


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
