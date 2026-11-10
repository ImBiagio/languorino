from django.contrib import admin

from .models import Job, JobFile


class JobFileInline(admin.TabularInline):
    model = JobFile
    extra = 0
    readonly_fields = ["file", "content_type", "original_name", "size"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["created_at", "kind", "status", "owner", "model"]
    list_filter = ["kind", "status"]
    search_fields = ["owner__email", "error"]
    readonly_fields = ["input", "result", "error", "model", "started_at", "finished_at"]
    inlines = [JobFileInline]
