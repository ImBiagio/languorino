from django.urls import path

from .views import (
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
]
