from django.urls import path

from .views import (
    NutritionistPlanConfirmView,
    NutritionistPlanDetailView,
    NutritionistPlanListView,
    PlanActivateView,
    PlanCurrentView,
    PlanDetailView,
    PlanListView,
    PlannedMealView,
    PlanRegenerateView,
    PlanRetryView,
)

urlpatterns = [
    path("plans", PlanListView.as_view(), name="plans"),
    path("plans/current", PlanCurrentView.as_view(), name="plan-current"),
    path("plans/<uuid:pk>", PlanDetailView.as_view(), name="plan-detail"),
    path("plans/<uuid:pk>/activate", PlanActivateView.as_view(), name="plan-activate"),
    path("plans/<uuid:pk>/regenerate", PlanRegenerateView.as_view(), name="plan-regenerate"),
    path("plans/<uuid:pk>/retry", PlanRetryView.as_view(), name="plan-retry"),
    path("plans/<uuid:pk>/meals/<int:meal_id>", PlannedMealView.as_view(), name="plan-meal"),
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
