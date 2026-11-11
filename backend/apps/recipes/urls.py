from django.urls import path

from .views import (
    IngredientSearchView,
    RecipeBookDetailView,
    RecipeBookImagesView,
    RecipeBookListView,
    RecipeBookRetryView,
    RecipeDetailView,
    RecipeImageDrawView,
    RecipeImageView,
    RecipeListView,
    RecipeSaveView,
    RecipeShareView,
    SharedRecipeCopyView,
    SharedRecipeView,
    TagDetailView,
    TagListView,
)

urlpatterns = [
    path("ingredients", IngredientSearchView.as_view(), name="ingredients"),
    path("recipes", RecipeListView.as_view(), name="recipes"),
    path("recipes/<uuid:pk>", RecipeDetailView.as_view(), name="recipe-detail"),
    path("recipes/<uuid:pk>/save", RecipeSaveView.as_view(), name="recipe-save"),
    path("recipes/<uuid:pk>/image", RecipeImageView.as_view(), name="recipe-image"),
    path("recipes/<uuid:pk>/share", RecipeShareView.as_view(), name="recipe-share"),
    path("shared/recipes/<str:token>", SharedRecipeView.as_view(), name="shared-recipe"),
    path(
        "shared/recipes/<str:token>/copy",
        SharedRecipeCopyView.as_view(),
        name="shared-recipe-copy",
    ),
    path("recipes/<uuid:pk>/image/draw", RecipeImageDrawView.as_view(), name="recipe-image-draw"),
    path("recipe-books", RecipeBookListView.as_view(), name="recipe-books"),
    path("recipe-books/<uuid:pk>", RecipeBookDetailView.as_view(), name="recipe-book-detail"),
    path("recipe-books/<uuid:pk>/retry", RecipeBookRetryView.as_view(), name="recipe-book-retry"),
    path(
        "recipe-books/<uuid:pk>/images", RecipeBookImagesView.as_view(), name="recipe-book-images"
    ),
    path("tags", TagListView.as_view(), name="tags"),
    path("tags/<uuid:pk>", TagDetailView.as_view(), name="tag-detail"),
]
