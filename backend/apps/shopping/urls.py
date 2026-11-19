from django.urls import path

from .views import (
    RecurringItemDetailView,
    RecurringItemListView,
    RecurringSuggestionsView,
    ShoppingItemDetailView,
    ShoppingItemListView,
    ShoppingListDetailView,
    ShoppingListRegenerateView,
    ShoppingListView,
)

urlpatterns = [
    path("shopping/recurring", RecurringItemListView.as_view(), name="shopping-recurring"),
    path(
        "shopping/recurring/suggestions",
        RecurringSuggestionsView.as_view(),
        name="shopping-recurring-suggestions",
    ),
    path(
        "shopping/recurring/<int:item_id>",
        RecurringItemDetailView.as_view(),
        name="shopping-recurring-item",
    ),
    path("shopping", ShoppingListView.as_view(), name="shopping"),
    path("shopping/<uuid:pk>", ShoppingListDetailView.as_view(), name="shopping-detail"),
    path(
        "shopping/<uuid:pk>/regenerate",
        ShoppingListRegenerateView.as_view(),
        name="shopping-regenerate",
    ),
    path("shopping/<uuid:pk>/items", ShoppingItemListView.as_view(), name="shopping-items"),
    path(
        "shopping/<uuid:pk>/items/<int:item_id>",
        ShoppingItemDetailView.as_view(),
        name="shopping-item",
    ),
]
