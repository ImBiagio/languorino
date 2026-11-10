from django.contrib import admin

from .models import FoodPreference, Profile


class FoodPreferenceInline(admin.TabularInline):
    model = FoodPreference
    extra = 0
    fields = ["kind", "label", "allergen"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "first_name",
        "last_name",
        "followed_by_nutritionist",
        "onboarding_completed_at",
    ]
    search_fields = ["user__email", "first_name", "last_name"]
    inlines = [FoodPreferenceInline]
