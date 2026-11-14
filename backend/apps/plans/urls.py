from django.urls import path

from .views import (
    AskView,
    NutritionistPlanConfirmView,
    NutritionistPlanDetailView,
    NutritionistPlanListView,
    PlanActivateView,
    PlanCurrentView,
    PlanDetailView,
    PlanListView,
    PlannedMealIdeasView,
    PlannedMealView,
    PlanRegenerateView,
    PlanRetryView,
    PlanShareDetailView,
    PlanShareListView,
    SharedPlanRecipeView,
    SharedPlanView,
)

urlpatterns = [
    path("ask", AskView.as_view(), name="ask"),
    path("plans", PlanListView.as_view(), name="plans"),
    path("plans/current", PlanCurrentView.as_view(), name="plan-current"),
    path("plans/<uuid:pk>", PlanDetailView.as_view(), name="plan-detail"),
    path("plans/<uuid:pk>/activate", PlanActivateView.as_view(), name="plan-activate"),
    path("plans/<uuid:pk>/regenerate", PlanRegenerateView.as_view(), name="plan-regenerate"),
    path("plans/<uuid:pk>/retry", PlanRetryView.as_view(), name="plan-retry"),
    path("plans/<uuid:pk>/meals/<int:meal_id>", PlannedMealView.as_view(), name="plan-meal"),
    path(
        "plans/<uuid:pk>/meals/<int:meal_id>/ideas",
        PlannedMealIdeasView.as_view(),
        name="plan-meal-ideas",
    ),
    path("plan-shares", PlanShareListView.as_view(), name="plan-shares"),
    path("plan-shares/<uuid:pk>", PlanShareDetailView.as_view(), name="plan-share-detail"),
    path("plan-shares/<uuid:pk>/plan", SharedPlanView.as_view(), name="shared-plan"),
    path(
        "plan-shares/<uuid:pk>/recipes/<uuid:recipe_id>",
        SharedPlanRecipeView.as_view(),
        name="shared-plan-recipe",
    ),
    path("nutritionist-plans", NutritionistPlanListView.as_view(), name="nutritionist-plans"),
    path(
        "nutritionist-plans/<uuid:pk>",
        NutritionistPlanDetailView.as_view(),
        name="nutritionist-plan-detail",
    ),
    path(
        "nutritionist-plans/<uuid:pk>/confirm",
        NutritionistPlanConfirmView.as_view(),
        name="nutritionist-plan-confirm",
    ),
]
