"""Lavori lunghi dell'utente (progettazione, principio 3).

Tutto cio' che chiama l'LLM gira in Celery: la richiesta crea un ``Job``,
risponde subito e il frontend ne segue lo stato. Un job che produce dati
(ricette lette da una foto) si ferma in ``ready`` con la bozza in ``result``:
diventa dati veri solo con la conferma dell'utente.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Job(BaseModel):
    class Kind(models.TextChoices):
        IMPORT_RECIPES = "import_recipes", _("Importa ricette")
        FRIDGE_SCAN = "fridge_scan", _("Leggi il frigo")
        COOK_IDEAS = "cook_ideas", _("Idee per cucinare")
        NUTRITIONIST_PLAN = "nutritionist_plan", _("Leggi il piano del nutrizionista")
        RECIPE_IMAGE = "recipe_image", _("Disegna la ricetta")
        INTERVIEW = "interview", _("Intervista per il profilo")
        MEAL_IDEAS = "meal_ideas", _("Idee per un pasto del piano")

    class Status(models.TextChoices):
        QUEUED = "queued", _("In coda")
        RUNNING = "running", _("In lavorazione")
        READY = "ready", _("Da rivedere")
        CONFIRMED = "confirmed", _("Confermato")
        FAILED = "failed", _("Non riuscito")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    # Parametri del lavoro (es. la lingua in cui rispondere).
    input = models.JSONField(default=dict, blank=True)
    # La bozza da rivedere e, dopo la conferma, cosa e' stato creato.
    result = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)
    model = models.CharField(max_length=60, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.get_status_display()})"


def job_upload_path(instance: JobFile, filename: str) -> str:
    # Nome casuale: il nome originale (magari "ricette di mamma.pdf") resta in
    # original_name e non finisce in un URL.
    return f"jobs/{instance.job_id}/{instance.id}{instance.extension}"


class JobFile(BaseModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=job_upload_path, max_length=200)
    content_type = models.CharField(max_length=40)
    original_name = models.CharField(max_length=200, blank=True)
    size = models.PositiveIntegerField(default=0)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    @property
    def extension(self) -> str:
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/heic": ".heic",
            "image/heif": ".heif",
            "application/pdf": ".pdf",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
        }.get(self.content_type, "")
