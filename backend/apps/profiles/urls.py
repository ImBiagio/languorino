from django.urls import path

from .views import PreferenceDetailView, PreferenceListView, ProfileCompleteView, ProfileView

urlpatterns = [
    path("profile", ProfileView.as_view(), name="profile"),
    path("profile/complete", ProfileCompleteView.as_view(), name="profile-complete"),
    path("profile/preferences", PreferenceListView.as_view(), name="profile-preferences"),
    path(
        "profile/preferences/<uuid:pk>",
        PreferenceDetailView.as_view(),
        name="profile-preference-detail",
    ),
]
