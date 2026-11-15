"""Stime AI per il frontend: proxy verso cornhub con l'utente della sessione.

Il frontend non parla mai con cornhub direttamente (le chiavi e i conti
stanno li'): chiede qui, e qui si aggiunge chi e' l'utente.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import cornhub


class AiQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wanted: dict[str, int] = {}
        for raw in request.query_params.get("features", "").split(",")[:20]:
            name, _, count = raw.strip().partition(":")
            if name:
                wanted[name] = max(1, min(int(count) if count.isdigit() else 1, 500))
        if not wanted:
            return Response({"detail": "features?"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fast = request.query_params.get("fast") in ("1", "true")
            return Response(cornhub.quote(wanted, user=request.user, fast=fast))
        except cornhub.AIError as exc:
            return Response({"detail": exc.message, "code": exc.code},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
