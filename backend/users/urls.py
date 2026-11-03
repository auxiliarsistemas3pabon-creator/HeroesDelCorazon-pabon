from django.urls import path

from . import views

# Prefijo /api/v1/ definido en config/urls.py. Las rutas auth/* usan cookies httpOnly (ver views.py).
urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/password-change/", views.PasswordChangeView.as_view(), name="password-change"),
    path("auth/password-reset/", views.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "auth/password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("users/areas/", views.AreasView.as_view(), name="areas"),
    path("users/staff-candidates/", views.StaffCandidatesView.as_view(), name="staff-candidates"),
    path("users/evaluators/", views.EvaluatorsView.as_view(), name="evaluators"),
    path("users/import/", views.StaffImportView.as_view(), name="staff-import"),
    path("users/register/", views.RegisterView.as_view(), name="register"),
    path("users/collaborators/", views.CollaboratorsView.as_view(), name="collaborators"),
]
