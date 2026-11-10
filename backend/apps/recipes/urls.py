from django.urls import path

from .views import (
    IngredientSearchView,
    RecipeDetailView,
    RecipeListView,
    TagDetailView,
    TagListView,
)

urlpatterns = [
    path("ingredients", IngredientSearchView.as_view(), name="ingredients"),
    path("recipes", RecipeListView.as_view(), name="recipes"),
    path("recipes/<uuid:pk>", RecipeDetailView.as_view(), name="recipe-detail"),
    path("tags", TagListView.as_view(), name="tags"),
    path("tags/<uuid:pk>", TagDetailView.as_view(), name="tag-detail"),
]
