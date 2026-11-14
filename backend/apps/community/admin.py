from django.contrib import admin

from .models import Comment, Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["recipe", "user", "stars", "updated_at"]
    raw_id_fields = ["recipe", "user"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["recipe", "author", "text", "created_at", "deleted_at"]
    raw_id_fields = ["recipe", "author", "parent"]
