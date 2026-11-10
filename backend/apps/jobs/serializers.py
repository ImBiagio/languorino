from __future__ import annotations

from rest_framework import serializers

from apps.recipes.serializers import RecipeSerializer

from .models import Job, JobFile


class JobFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFile
        fields = ["id", "content_type", "original_name", "size"]
        read_only_fields = fields


class JobSerializer(serializers.ModelSerializer):
    files = JobFileSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "kind",
            "status",
            "result",
            "error",
            "files",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class ImportConfirmSerializer(serializers.Serializer):
    """Le ricette che l'utente tiene, come le ha corrette nel form di revisione."""

    recipes = RecipeSerializer(many=True, min_length=1, max_length=20)
