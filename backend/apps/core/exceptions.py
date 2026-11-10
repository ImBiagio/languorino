from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """Traduce le ValidationError di Django (model.clean) in errori DRF 400.

    Serve perche' i vincoli dei modelli vivono in ``Model.clean()``: senza questo
    handler arriverebbero al client come 500.
    """
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        exc = exceptions.ValidationError(detail)
    return drf_exception_handler(exc, context)
