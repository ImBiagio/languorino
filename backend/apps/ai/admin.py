from django.contrib import admin

from .models import AiCall


@admin.register(AiCall)
class AiCallAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "feature",
        "model",
        "user",
        "input_tokens",
        "output_tokens",
        "duration_ms",
        "ok",
        "service_tier",
    ]
    list_filter = ["feature", "model", "ok", "service_tier"]
    search_fields = ["user__email", "error"]
