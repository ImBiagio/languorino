from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    RefreshView,
    RegisterView,
    ResendVerificationView,
    VerifyEmailView,
)

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    # "resend" prima del token: altrimenti finirebbe in <str:token>.
    path(
        "auth/verify-email/resend", ResendVerificationView.as_view(), name="auth-verify-resend"
    ),
    path("auth/verify-email/<str:token>", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/password", PasswordChangeView.as_view(), name="auth-password"),
    path("auth/password-reset", PasswordResetView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("me", MeView.as_view(), name="me"),
]
