from __future__ import annotations

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import is_enabled
from apps.jobs.files import FileRejected, prepare
from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer
from apps.jobs.views import enqueue_job, save_job_files
from apps.recipes.models import Recipe, RecipeIngredient

from .ask import MAX_MESSAGE_CHARS as ASK_MAX_MESSAGE_CHARS
from .ask import MAX_MESSAGES as ASK_MAX_MESSAGES
from .models import MealPlan, NutritionistPlan, PlannedMeal, current_plan
from .serializers import (
    MealPlanDetailSerializer,
    MealPlanSerializer,
    NutritionistPlanSerializer,
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
        plan = current_plan(request.user)
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


# --- piano del nutrizionista (ADR 0010) ---------------------------------------------------


def nutritionist_plans_of(user):
    return (
        NutritionistPlan.objects.filter(owner=user)
        .select_related("job")
        .prefetch_related("job__files")
    )


class NutritionistPlanListView(APIView):
    """I piani del nutrizionista; POST con PDF o foto avvia la lettura (job)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_throttles(self):
        self.throttle_scope = "ai" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: NutritionistPlanSerializer(many=True)})
    def get(self, request):
        plans = nutritionist_plans_of(request.user)[:20]
        return Response(NutritionistPlanSerializer(plans, many=True).data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                },
            }
        },
        responses={202: JobSerializer},
    )
    def post(self, request):
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            prepared = prepare(request.FILES.getlist("files"))
        except FileRejected as exc:
            raise serializers.ValidationError({"files": str(exc)}) from exc
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.NUTRITIONIST_PLAN,
                input={"language": (get_language() or "it")[:2]},
            )
            save_job_files(job, prepared)
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class NutritionistPlanDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def _get(self, request, pk) -> NutritionistPlan:
        return get_object_or_404(nutritionist_plans_of(request.user), pk=pk)

    @extend_schema(responses={200: NutritionistPlanSerializer})
    def get(self, request, pk):
        return Response(NutritionistPlanSerializer(self._get(request, pk)).data)

    @extend_schema(request=NutritionistPlanSerializer, responses={200: NutritionistPlanSerializer})
    def patch(self, request, pk):
        plan = self._get(request, pk)
        data = NutritionistPlanSerializer(plan, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        return Response(data.data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        """Via il piano e i file da cui e' stato letto; i piani generati restano."""
        plan = self._get(request, pk)
        with transaction.atomic():
            job = plan.job
            plan.delete(hard=True)
            if job is not None:
                for item in job.files.all():
                    item.file.delete(save=False)
                job.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NutritionistPlanConfirmView(APIView):
    """La bozza riletta diventa il piano da seguire."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: NutritionistPlanSerializer})
    def post(self, request, pk):
        plan = get_object_or_404(nutritionist_plans_of(request.user), pk=pk)
        if not plan.rules.get("meals"):
            raise serializers.ValidationError(
                {"rules": _("Serve almeno un pasto con le sue opzioni.")}
            )
        plan.status = NutritionistPlan.Status.CONFIRMED
        plan.save(update_fields=["status", "updated_at"])
        if plan.job is not None and plan.job.status == Job.Status.READY:
            plan.job.status = Job.Status.CONFIRMED
            plan.job.save(update_fields=["status", "updated_at"])
        return Response(NutritionistPlanSerializer(plan).data)


class NutritionistPlanRereadView(APIView):
    """Rilegge i file del piano (per esempio per prendere le sostituzioni, che
    prima finivano nelle note): le regole nuove tornano da rivedere."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: JobSerializer})
    def post(self, request, pk):
        plan = get_object_or_404(nutritionist_plans_of(request.user), pk=pk)
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if plan.job is None or not plan.job.files.exists():
            raise serializers.ValidationError(
                {"detail": _("I file di questo piano non ci sono più: caricalo di nuovo.")}
            )
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.NUTRITIONIST_PLAN,
                input={"plan": str(plan.id), "language": (get_language() or "it")[:2]},
            )
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class PlannedMealIdeasView(APIView):
    """Ricette nuove per un pasto del piano, scritte dall'LLM in un job."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_scope = "ai"

    @extend_schema(request=dict, responses={202: JobSerializer})
    def post(self, request, pk, meal_id):
        plan = get_object_or_404(plans_of(request.user), pk=pk)
        meal = get_object_or_404(plan.meals, id=meal_id)
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        hint = " ".join(str(request.data.get("hint", "")).split())[:200]
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.MEAL_IDEAS,
                input={
                    "plan": str(plan.id),
                    "meal": meal.id,
                    "hint": hint,
                    "language": (get_language() or "it")[:2],
                },
            )
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class AskMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["assistant", "user"])
    text = serializers.CharField(max_length=ASK_MAX_MESSAGE_CHARS, allow_blank=True)


class AskView(APIView):
    """Una domanda alla chat (ADR 0016): la conversazione finora, che vive nel
    browser. Risponde con un job; la risposta e' in ``result.reply``."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_scope = "ai"

    @extend_schema(request=AskMessageSerializer(many=True), responses={202: JobSerializer})
    def post(self, request):
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        messages = AskMessageSerializer(data=request.data.get("messages", []), many=True)
        messages.is_valid(raise_exception=True)
        history = list(messages.validated_data)[-ASK_MAX_MESSAGES:]
        if not (history and history[-1]["role"] == "user" and history[-1]["text"].strip()):
            raise serializers.ValidationError({"messages": _("Scrivi una domanda.")})
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.ASK,
                input={
                    "messages": [dict(message) for message in history],
                    "language": (get_language() or "it")[:2],
                },
            )
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
