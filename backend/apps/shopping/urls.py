from django.urls import path

from .views import (
    ShoppingItemDetailView,
    ShoppingItemListView,
    ShoppingListDetailView,
    ShoppingListRegenerateView,
    ShoppingListView,
)

urlpatterns = [
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
