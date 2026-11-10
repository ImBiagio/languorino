from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import is_enabled
from apps.jobs.files import PDF, FileRejected, prepare
from apps.jobs.models import Job, JobFile
from apps.jobs.serializers import JobSerializer
from apps.jobs.views import enqueue_job
from apps.profiles.models import MealSlot
from apps.recipes.serializers import RecipeListSerializer

from .cook_today import MAX_INGREDIENTS, clean_names, match_recipes

MAX_PHOTOS = 3


class SuggestSerializer(serializers.Serializer):
    ingredients = serializers.ListField(
        child=serializers.CharField(max_length=80, allow_blank=True), max_length=MAX_INGREDIENTS
    )
    slot = serializers.ChoiceField(choices=MealSlot.choices, required=False, allow_null=True)
    minutes = serializers.IntegerField(min_value=5, max_value=300, required=False, allow_null=True)
    servings = serializers.IntegerField(min_value=1, max_value=12, default=2)
    include_books = serializers.BooleanField(default=True)
    ideas = serializers.BooleanField(default=True)

    def validate_ingredients(self, value):
        names = clean_names(value)
        if not names:
            raise serializers.ValidationError(_("Scrivi almeno un ingrediente."))
        return names


def _disabled() -> Response:
    return Response(
        {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class FridgeScanView(APIView):
    """Foto del frigo -> job che elenca gli alimenti (da correggere a mano)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_scope = "ai"

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
            return _disabled()
        uploads = request.FILES.getlist("files")
        if len(uploads) > MAX_PHOTOS:
            raise serializers.ValidationError(
                {"files": _("Al massimo %(n)d foto.") % {"n": MAX_PHOTOS}}
            )
        try:
            prepared = prepare(uploads)
        except FileRejected as exc:
            raise serializers.ValidationError({"files": str(exc)}) from exc
        if any(kind == PDF for _data, kind, _name in prepared):
            raise serializers.ValidationError({"files": _("Qui servono foto, non PDF.")})
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.FRIDGE_SCAN,
                input={"language": (get_language() or "it")[:2]},
            )
            for position, (data, content_type, name) in enumerate(prepared):
                item = JobFile(
                    job=job,
                    content_type=content_type,
                    original_name=name,
                    size=len(data),
                    position=position,
                )
                item.file.save("upload", ContentFile(data), save=False)
                item.save()
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class SuggestView(APIView):
    """Le ricette che si possono fare (subito, dal codice) e le idee nuove (job)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_throttles(self):
        # Solo se si chiedono idee nuove si consuma quota dell'LLM.
        self.throttle_scope = "ai" if self.request.data.get("ideas", True) else None
        return super().get_throttles()

    @extend_schema(request=SuggestSerializer)
    def post(self, request):
        data = SuggestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        options = data.validated_data
        matches = match_recipes(
            request.user,
            options["ingredients"],
            slot=options.get("slot"),
            minutes=options.get("minutes"),
            include_books=options["include_books"],
        )
        job = None
        if options["ideas"] and is_enabled():
            with transaction.atomic():
                job = Job.objects.create(
                    owner=request.user,
                    kind=Job.Kind.COOK_IDEAS,
                    input={
                        "ingredients": options["ingredients"],
                        "slot": options.get("slot"),
                        "minutes": options.get("minutes"),
                        "servings": options["servings"],
                        "language": (get_language() or "it")[:2],
                    },
                )
                enqueue_job(job)
            job.refresh_from_db()
        context = {"request": request}
        return Response(
            {
                "ingredients": options["ingredients"],
                "matches": [
                    {
                        "recipe": RecipeListSerializer(item["recipe"], context=context).data,
                        "have": item["have"],
                        "missing": item["missing"],
                    }
                    for item in matches
                ],
                "job": JobSerializer(job).data if job else None,
            }
        )
