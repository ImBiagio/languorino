from django.urls import path

from .views import (
    InterviewLiveView,
    InterviewProposalView,
    InterviewView,
    PreferenceDetailView,
    PreferenceListView,
    ProfileCompleteView,
    ProfileView,
)

urlpatterns = [
    path("profile", ProfileView.as_view(), name="profile"),
    path("profile/complete", ProfileCompleteView.as_view(), name="profile-complete"),
    path("profile/interview", InterviewView.as_view(), name="profile-interview"),
    path("profile/interview/live", InterviewLiveView.as_view(), name="profile-interview-live"),
    path(
        "profile/interview/proposal",
        InterviewProposalView.as_view(),
        name="profile-interview-proposal",
    ),
    path("profile/preferences", PreferenceListView.as_view(), name="profile-preferences"),
    path(
        "profile/preferences/<uuid:pk>",
        PreferenceDetailView.as_view(),
        name="profile-preference-detail",
    ),
]
