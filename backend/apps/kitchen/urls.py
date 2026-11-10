from django.urls import path

from .views import FridgeScanView, SuggestView

urlpatterns = [
    path("cook-today/scan", FridgeScanView.as_view(), name="cook-today-scan"),
    path("cook-today/suggest", SuggestView.as_view(), name="cook-today-suggest"),
]
