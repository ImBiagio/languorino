"""Registro delle chiamate all'LLM: quanto costa ogni funzione, e a chi."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AiCall(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_calls",
    )
    # Cosa si e' chiesto: "import_recipes", piu' avanti "plan_week", ...
    feature = models.CharField(max_length=40, db_index=True)
    model = models.CharField(max_length=60, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.feature} {self.model} {'ok' if self.ok else 'ko'}"
