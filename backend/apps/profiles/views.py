from __future__ import annotations

import json

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import AIError, is_enabled
from apps.jobs.files import FileRejected, prepare_audio
from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer
from apps.jobs.views import enqueue_job, save_job_files

from .interview import MAX_MESSAGE_CHARS, MAX_MESSAGES
from .live import clean_call, live_token
from .models import FoodPreference, Profile
from .serializers import FoodPreferenceSerializer, ProfileSerializer


def profile_of(user) -> Profile:
    """Il profilo nasce vuoto alla prima richiesta: niente segnali sulla registrazione."""
    profile, _created = Profile.objects.get_or_create(user=user)
    return profile


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProfileSerializer})
    def get(self, request):
        return Response(ProfileSerializer(profile_of(request.user)).data)

    @extend_schema(request=ProfileSerializer, responses={200: ProfileSerializer})
    def patch(self, request):
        serializer = ProfileSerializer(profile_of(request.user), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProfileCompleteView(APIView):
    """Fine del wizard: da qui in poi l'app apre la home."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ProfileSerializer})
    def post(self, request):
        profile = profile_of(request.user)
        if profile.onboarding_completed_at is None:
            profile.onboarding_completed_at = timezone.now()
            profile.save(update_fields=["onboarding_completed_at", "updated_at"])
        return Response(ProfileSerializer(profile).data)


class PreferenceListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: FoodPreferenceSerializer(many=True)})
    def get(self, request):
        preferences = profile_of(request.user).preferences.all()
        return Response(FoodPreferenceSerializer(preferences, many=True).data)

    @extend_schema(
        request=FoodPreferenceSerializer,
        responses={200: FoodPreferenceSerializer, 201: FoodPreferenceSerializer},
    )
    def post(self, request):
        profile = profile_of(request.user)
        serializer = FoodPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # La stessa voce due volte (anche con maiuscole diverse) rimanda quella
        # che c'e' gia': un doppio tocco sul chip non deve dare errore.
        existing = profile.preferences.filter(
            kind=serializer.validated_data["kind"],
            label__iexact=serializer.validated_data["label"],
        ).first()
        if existing:
            return Response(FoodPreferenceSerializer(existing).data)
        preference = serializer.save(profile=profile)
        return Response(FoodPreferenceSerializer(preference).data, status=status.HTTP_201_CREATED)


class PreferenceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        preference = get_object_or_404(FoodPreference, pk=pk, profile__user=request.user)
        # Cancellata davvero: una preferenza tolta non e' storia da tenere.
        preference.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InterviewMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["assistant", "user"])
    text = serializers.CharField(max_length=MAX_MESSAGE_CHARS, allow_blank=True)


class InterviewView(APIView):
    """Un turno dell'intervista (ADR 0013): la conversazione finora e, se si
    parla, la registrazione dell'ultima risposta. Risponde con un job."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_scope = "ai"

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "messages": {"type": "string", "description": "JSON [{role, text}]"},
                    "audio": {"type": "string", "format": "binary"},
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
        raw = request.data.get("messages", [])
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"messages": _("Conversazione non valida.")}
                ) from exc
        messages = InterviewMessageSerializer(data=raw, many=True)
        messages.is_valid(raise_exception=True)
        history = list(messages.validated_data)[-MAX_MESSAGES:]
        audio = request.FILES.get("audio")
        if audio is None and not (
            history and history[-1]["role"] == "user" and history[-1]["text"].strip()
        ):
            raise serializers.ValidationError({"messages": _("Scrivi o registra una risposta.")})
        prepared = []
        if audio is not None:
            try:
                prepared = [prepare_audio(audio)]
            except FileRejected as exc:
                raise serializers.ValidationError({"audio": str(exc)}) from exc
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.INTERVIEW,
                input={
                    "messages": [dict(message) for message in history],
                    "language": (get_language() or "it")[:2],
                },
            )
            save_job_files(job, prepared)
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class InterviewLiveView(APIView):
    """Apre una conversazione a voce in tempo reale (ADR 0014): un token
    monouso con modello, istruzioni e strumenti gia' decisi qui."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={200: dict})
    def post(self, request):
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            session = live_token(request.user, (get_language() or "it")[:2])
        except AIError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(session)


class InterviewProposalView(APIView):
    """Pulisce una chiamata agli strumenti arrivata dalla conversazione a voce
    (``{name, args}``), con le regole della chat: il browser la mette nel
    riepilogo, non la salva."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(request=dict, responses={200: dict})
    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        return Response(clean_call(request.user, str(data.get("name", "")), args))
