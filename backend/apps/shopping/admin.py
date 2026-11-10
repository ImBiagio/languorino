from django.contrib import admin

from .models import ShoppingItem, ShoppingList


class ShoppingItemInline(admin.TabularInline):
    model = ShoppingItem
    extra = 0
    raw_id_fields = ["ingredient"]
    exclude = ["sources"]


@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "date_from", "date_to"]
    list_filter = ["status"]
    search_fields = ["title", "owner__email"]
    inlines = [ShoppingItemInline]
