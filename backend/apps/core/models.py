from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):  # type: ignore[override]
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class NotDeletedManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Manager di default: nasconde i record cancellati logicamente."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    pass


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = NotDeletedManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, hard: bool = False):  # type: ignore[override]
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self) -> None:
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
