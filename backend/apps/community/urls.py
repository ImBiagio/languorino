from django.urls import path

from .views import CommentDetailView, PublicProfileView, RecipeCommentsView, RecipeRatingView

urlpatterns = [
    path("public/profiles/<str:handle>", PublicProfileView.as_view(), name="public-profile"),
    path(
        "shared/recipes/<str:token>/comments",
        RecipeCommentsView.as_view(),
        name="shared-recipe-comments",
    ),
    path(
        "shared/recipes/<str:token>/rating", RecipeRatingView.as_view(), name="shared-recipe-rating"
    ),
    path("comments/<uuid:pk>", CommentDetailView.as_view(), name="comment-detail"),
]
