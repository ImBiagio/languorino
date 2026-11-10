from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
