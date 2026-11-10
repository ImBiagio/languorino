from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import is_enabled
from apps.recipes.models import Recipe

from .files import PDF, FileRejected, prepare
from .models import Job, JobFile
from .serializers import ImportConfirmSerializer, JobSerializer
from .tasks import run_job


def save_job_files(job: Job, prepared: list[tuple[bytes, str, str]]) -> None:
    """I file gia' controllati da ``prepare``, nell'ordine in cui sono arrivati."""
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


def enqueue_job(job: Job) -> None:
    # Dopo il commit: il worker deve trovare job e file gia' salvati.
    transaction.on_commit(lambda: run_job.delay(str(job.id)))


class JobListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_throttles(self):
        # Solo la creazione chiama l'LLM e consuma quota; leggere lo stato e' libero.
        self.throttle_scope = "ai" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(
        parameters=[OpenApiParameter("status", str, many=True), OpenApiParameter("kind", str)],
        responses={200: JobSerializer(many=True)},
    )
    def get(self, request):
        jobs = Job.objects.filter(owner=request.user).prefetch_related("files")
        if statuses := request.query_params.getlist("status"):
            jobs = jobs.filter(status__in=statuses)
        if kind := request.query_params.get("kind"):
            jobs = jobs.filter(kind=kind)
        return Response(JobSerializer(jobs[:20], many=True).data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
                },
            }
        },
        responses={202: JobSerializer},
    )
    def post(self, request):
        kind = request.data.get("kind")
        # Gli altri lavori hanno i loro endpoint (es. /api/cook-today/...).
        if kind != Job.Kind.IMPORT_RECIPES:
            raise serializers.ValidationError({"kind": _("Lavoro sconosciuto.")})
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
                kind=kind,
                input={"language": (get_language() or "it")[:2]},
            )
            save_job_files(job, prepared)
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


def job_of(request, pk) -> Job:
    return get_object_or_404(Job.objects.prefetch_related("files"), pk=pk, owner=request.user)


class JobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: JobSerializer})
    def get(self, request, pk):
        return Response(JobSerializer(job_of(request, pk)).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        """Scarta il lavoro e i suoi file (le ricette gia' confermate restano)."""
        job = job_of(request, pk)
        for item in job.files.all():
            item.file.delete(save=False)
        job.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobRetryView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: JobSerializer})
    def post(self, request, pk):
        job = job_of(request, pk)
        if job.status != Job.Status.FAILED:
            raise serializers.ValidationError(
                {"detail": _("Si può riprovare solo un lavoro non riuscito.")}
            )
        job.status = Job.Status.QUEUED
        job.error = ""
        job.result = {}
        job.save(update_fields=["status", "error", "result", "updated_at"])
        enqueue_job(job)
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class JobConfirmView(APIView):
    """Le bozze riviste diventano ricette del ricettario."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=ImportConfirmSerializer, responses={201: JobSerializer})
    def post(self, request, pk):
        job = job_of(request, pk)
        if job.kind != Job.Kind.IMPORT_RECIPES or job.status != Job.Status.READY:
            raise serializers.ValidationError({"detail": _("Non c'è niente da confermare.")})
        serializer = ImportConfirmSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        source = (
            Recipe.Source.PDF
            if job.files.exists() and not job.files.exclude(content_type=PDF).exists()
            else Recipe.Source.PHOTO
        )
        with transaction.atomic():
            created = [
                serializer.fields["recipes"].child.create(
                    {**data, "owner": request.user, "source": source}
                )
                for data in serializer.validated_data["recipes"]
            ]
            job.status = Job.Status.CONFIRMED
            job.result = {**job.result, "created": [str(recipe.id) for recipe in created]}
            job.save(update_fields=["status", "result", "updated_at"])
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)
