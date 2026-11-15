from django.urls import path

from .sso import SSOCallbackView, SSOStartView
from .views import AuthConfigView, LogoutView, MeView, RefreshView

urlpatterns = [
    path("auth/config", AuthConfigView.as_view(), name="auth-config"),
    path("auth/sso/start", SSOStartView.as_view(), name="auth-sso-start"),
    path("auth/sso/callback", SSOCallbackView.as_view(), name="auth-sso-callback"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="me"),
]
