from django.apps import AppConfig


class ShoppingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shopping"

    def ready(self):
        from . import signals  # noqa: F401  (rinvii a Scontrino, ADR 0026)
