from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import is_enabled
from apps.recipes.models import Recipe, RecipeIngredient

from .models import MealPlan, PlannedMeal
from .serializers import (
    MealPlanDetailSerializer,
    MealPlanSerializer,
    PlannedMealSerializer,
    PlanSettingsSerializer,
)
from .tasks import enqueue_plan


def plans_of(user):
    return MealPlan.objects.filter(owner=user)


def with_meals(queryset):
    recipes = Recipe.all_objects.select_related("book").prefetch_related(
        "tags",
        Prefetch(
            "ingredients",
            queryset=RecipeIngredient.objects.select_related("ingredient").order_by("position"),
        ),
    )
    return queryset.prefetch_related(
        Prefetch(
            "meals",
            queryset=PlannedMeal.objects.prefetch_related(Prefetch("recipe", queryset=recipes)),
        )
    )


def _detail(request, plan: MealPlan, code=status.HTTP_200_OK) -> Response:
    plan = with_meals(plans_of(request.user)).get(pk=plan.pk)
    return Response(MealPlanDetailSerializer(plan, context={"request": request}).data, status=code)


class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        self.throttle_scope = "ai" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: MealPlanSerializer(many=True)})
    def get(self, request):
        return Response(MealPlanSerializer(plans_of(request.user)[:30], many=True).data)

    @extend_schema(request=PlanSettingsSerializer, responses={202: MealPlanDetailSerializer})
    def post(self, request):
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        options = PlanSettingsSerializer(data=request.data, context={"request": request})
        options.is_valid(raise_exception=True)
        with transaction.atomic():
            plan = MealPlan.objects.create(
                owner=request.user,
                start_date=options.validated_data["start_date"],
                days=options.validated_data["days"],
                settings=options.to_settings(),
                language=(get_language() or "it")[:2],
            )
            enqueue_plan(plan)
        return _detail(request, plan, status.HTTP_202_ACCEPTED)


class PlanCurrentView(APIView):
    """Il piano attivo per oggi (la home "Oggi"); 204 se non ce n'e'."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MealPlanDetailSerializer, 204: None})
    def get(self, request):
        active = plans_of(request.user).filter(status=MealPlan.Status.ACTIVE)
        today = date.today()
        # Quello che copre oggi; altrimenti il prossimo che deve ancora iniziare.
        plan = (
            next(
                (
                    p
                    for p in active
                    if p.start_date <= today < p.start_date + timedelta(days=p.days)
                ),
                None,
            )
            or active.filter(start_date__gt=today).order_by("start_date").first()
        )
        if plan is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return _detail(request, plan)


class PlanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MealPlanDetailSerializer})
    def get(self, request, pk):
        return _detail(request, get_object_or_404(plans_of(request.user), pk=pk))

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        plan = get_object_or_404(plans_of(request.user), pk=pk)
        with transaction.atomic():
            # Le ricette scritte per il piano e mai salvate se ne vanno con lui.
            written = Recipe.objects.filter(
                owner=request.user,
                source=Recipe.Source.PLAN,
                in_cookbook=False,
                id__in=plan.meals.values("recipe_id"),
            )
            plan.delete(hard=True)
            for recipe in written:
                recipe.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanActivateView(APIView):
    """La bozza diventa il piano in uso; quelli attivi prima si archiviano."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: MealPlanDetailSerializer})
    def post(self, request, pk):
        plan = get_object_or_404(plans_of(request.user), pk=pk)
        if plan.status not in (MealPlan.Status.DRAFT, MealPlan.Status.ARCHIVED):
            raise serializers.ValidationError({"detail": _("Il piano non è pronto.")})
        with transaction.atomic():
            plans_of(request.user).filter(status=MealPlan.Status.ACTIVE).exclude(pk=plan.pk).update(
                status=MealPlan.Status.ARCHIVED
            )
            plan.status = MealPlan.Status.ACTIVE
            plan.save(update_fields=["status", "updated_at"])
        return _detail(request, plan)


class PlanRegenerateView(APIView):
    """Rifa tutto il piano con le stesse scelte (solo bozze e piani interrotti)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: MealPlanDetailSerializer})
    def post(self, request, pk):
        plan = get_object_or_404(plans_of(request.user), pk=pk)
        if plan.status not in (MealPlan.Status.DRAFT, MealPlan.Status.FAILED):
            raise serializers.ValidationError(
                {"detail": _("Si rifà solo una bozza o un piano interrotto.")}
            )
        with transaction.atomic():
            plan.meals.all().delete()
            plan.weeks_done = 0
            plan.status = MealPlan.Status.GENERATING
            plan.error = ""
            plan.save()
            enqueue_plan(plan)
        return _detail(request, plan, status.HTTP_202_ACCEPTED)


class PlanRetryView(APIView):
    """Riprende un piano interrotto dalla settimana a cui era arrivato."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: MealPlanDetailSerializer})
    def post(self, request, pk):
        plan = get_object_or_404(plans_of(request.user), pk=pk)
        if plan.status != MealPlan.Status.FAILED:
            raise serializers.ValidationError(
                {"detail": _("Si può riprendere solo un piano interrotto.")}
            )
        with transaction.atomic():
            plan.status = MealPlan.Status.GENERATING
            plan.error = ""
            plan.save(update_fields=["status", "error", "updated_at"])
            enqueue_plan(plan)
        return _detail(request, plan, status.HTTP_202_ACCEPTED)


class PlannedMealView(APIView):
    """Cambiare un pasto a mano: un'altra ricetta, nessuna, porzioni, giorno di cottura."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=PlannedMealSerializer, responses={200: PlannedMealSerializer})
    def patch(self, request, pk, meal_id):
        meal = get_object_or_404(
            PlannedMeal.objects.select_related("plan"),
            pk=meal_id,
            plan_id=pk,
            plan__owner=request.user,
        )
        serializer = PlannedMealSerializer(meal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "recipe_id" in data:
            recipe_id = data.pop("recipe_id")
            meal.recipe = (
                get_object_or_404(Recipe, pk=recipe_id, owner=request.user) if recipe_id else None
            )
            meal.note = "" if meal.recipe else _("Pasto libero.")
        for field, value in data.items():
            setattr(meal, field, value)
        meal.save()
        meal = with_meals(plans_of(request.user)).get(pk=pk).meals.get(pk=meal.pk)
        return Response(PlannedMealSerializer(meal, context={"request": request}).data)
