from django.urls import path

from .views import (
    ChangePasswordView,
    CompanyProfileView,
    CsrfView,
    LiveHealthView,
    LoginView,
    LogoutView,
    MeView,
    ReadyHealthView,
)

urlpatterns = [
    path("health/live/", LiveHealthView.as_view(), name="health-live"),
    path("health/ready/", ReadyHealthView.as_view(), name="health-ready"),
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("company/", CompanyProfileView.as_view(), name="company-profile"),
]
