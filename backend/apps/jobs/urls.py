from django.urls import path

from .views import JobConfirmView, JobDetailView, JobListView, JobRetryView

urlpatterns = [
    path("jobs", JobListView.as_view(), name="jobs"),
    path("jobs/<uuid:pk>", JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/retry", JobRetryView.as_view(), name="job-retry"),
    path("jobs/<uuid:pk>/confirm", JobConfirmView.as_view(), name="job-confirm"),
]
