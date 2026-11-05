"""Vistas de autenticación, cuentas y directorios de usuarios para /api/v1/."""

import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from audit.mixins import AuditLogMixin
from common.permissions import IsBossOrSuperAdmin, IsSuperAdmin

from .areas import is_removed_area
from .models import User
from .serializers import (
    AuthenticatedUserSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .staff_import import StaffFileError, import_staff

logger = logging.getLogger(__name__)

# La cookie de refresh solo viaja a /api/v1/auth/*, reduciendo su exposicion al resto de la API.
REFRESH_COOKIE_PATH = "/api/v1/auth/"


def _set_auth_cookies(response, refresh: RefreshToken):
    """Escribe access y refresh como cookies httpOnly; el JS del frontend nunca ve los tokens."""
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        str(refresh.access_token),
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def _clear_auth_cookies(response):
    """Borra las cookies de sesion; el path debe coincidir con el usado al crearlas o el navegador no las elimina."""
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS_NAME)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH_NAME, path=REFRESH_COOKIE_PATH)


class LoginView(AuditLogMixin, APIView):
    """POST /auth/login/: autentica con username y contraseña y emite cookies JWT httpOnly.

    Es pública, limitada por tasa y protegida contra intentos repetidos por django-axes.
    No incluye los tokens en el cuerpo de respuesta; registra el resultado sin registrar credenciales.
    """
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = authenticate(request=request, **serializer.validated_data)
        except PermissionDenied:  # django-axes: account temporarily locked
            return Response(
                {"detail": _("Too many failed attempts. Try again later.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user is None or not user.is_active:
            return Response(
                {"detail": _("Invalid credentials.")}, status=status.HTTP_401_UNAUTHORIZED
            )

        get_token(request)  # forces the csrftoken cookie for the frontend
        response = Response(AuthenticatedUserSerializer(user).data)
        _set_auth_cookies(response, RefreshToken.for_user(user))
        return response


class RefreshView(AuditLogMixin, APIView):
    """POST /auth/refresh/: invalida el refresh token anterior y emite cookies JWT nuevas."""
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if not raw:
            return Response({"detail": _("No active session.")}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            old = RefreshToken(raw)
            user = User.objects.get(pk=old["user_id"], is_active=True)
            old.blacklist()
        except (TokenError, User.DoesNotExist):
            return Response({"detail": _("Session expired.")}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response({"detail": "ok"})
        _set_auth_cookies(response, RefreshToken.for_user(user))
        return response


class LogoutView(AuditLogMixin, APIView):
    """POST /auth/logout/: invalida el refresh token si existe y elimina las cookies de sesión."""
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_auth_cookies(response)
        return response


class MeView(AuditLogMixin, APIView):
    """GET /auth/me/: devuelve el usuario autenticado y establece la cookie CSRF para futuras mutaciones."""
    def get(self, request):
        get_token(request)
        return Response(AuthenticatedUserSerializer(request.user).data)


class RegisterView(AuditLogMixin, generics.CreateAPIView):
    """POST /users/register/: permite que un superadmin cree una cuenta colaboradora."""

    serializer_class = RegisterSerializer
    permission_classes = [IsSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class StaffImportView(AuditLogMixin, APIView):
    """POST /users/import/: superadmin importa personal desde Excel dentro de una transacción.

    Los documentos existentes se omiten; errores de formato se devuelven como HTTP 400.
    """

    permission_classes = [IsSuperAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if file is None:
            return Response({"detail": _("Attach an Excel file (.xlsx).")}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                result = import_staff(file)
        except StaffFileError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class AreasView(AuditLogMixin, APIView):
    """GET /users/areas/: lista áreas activas para sugerencias del formulario de registro."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        areas = (
            User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True)
            .exclude(area="")
            .order_by("area")
            .values_list("area", flat=True)
            .distinct()
        )
        return Response([area for area in areas if not is_removed_area(area)])


class StaffCandidatesView(AuditLogMixin, APIView):
    """GET /users/staff-candidates/: jefe o superadmin consulta personas activas que pueden evaluarse."""

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        staff = (
            User.objects.filter(role=User.Role.PERSONAL, is_active=True)
            .exclude(area="")
            .order_by("first_name", "last_name", "id")
            .values("id", "first_name", "last_name", "area")
        )
        return Response([person for person in staff if not is_removed_area(person["area"])])


class EvaluatorsView(AuditLogMixin, APIView):
    """GET /users/evaluators/: jefe o superadmin consulta colaboradores activos para programar evaluadores."""

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        evaluators = (
            User.objects.filter(role=User.Role.COLLABORATOR, is_active=True)
            .exclude(area="")
            .order_by("first_name", "last_name", "id")
            .values("id", "first_name", "last_name", "area")
        )
        return Response([person for person in evaluators if not is_removed_area(person["area"])])


class CollaboratorsView(generics.ListAPIView):
    """GET /users/collaborators/: lista compañeros activos de la misma área, excluyendo al usuario actual."""

    serializer_class = UserSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        # Sin area asignada no se lista a nadie, para no exponer colaboradores de otras areas.
        qs = User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True).exclude(pk=user.pk)
        return qs.filter(area=user.area) if user.area else qs.none()


class PasswordChangeView(AuditLogMixin, APIView):
    """POST /auth/password-change/: cambia la contraseña propia y limpia el indicador de clave temporal."""
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request, "target_user": request.user}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.password_change_required = False
        request.user.save(update_fields=["password", "password_change_required"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(AuditLogMixin, APIView):
    """POST /auth/password-reset/: solicita por correo un enlace de recuperación.

    Siempre devuelve HTTP 200 para no revelar si la dirección existe; aplica limitación de tasa.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"
            try:
                send_mail(
                    subject=_("Password recovery - Heroes del Corazon"),
                    message=_(
                        "Hello %(name)s,\n\n"
                        "We received a request to reset your password. "
                        "Open the following link:\n\n%(link)s\n\n"
                        "If it was not you, ignore this email."
                    )
                    % {"name": user.first_name, "link": link},
                    from_email=None,
                    recipient_list=[user.email],
                )
            except Exception:
                logger.exception("Could not send the password recovery email")

        return Response(
            {"detail": _("If the email exists, you will receive a link to reset your password.")}
        )


class PasswordResetConfirmView(AuditLogMixin, APIView):
    """POST /auth/password-reset/confirm/: valida uid y token, aplica reglas y guarda la nueva contraseña."""
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data["uid"])))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"detail": _("The link is invalid or has expired.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        check = PasswordChangeSerializer(
            data={"new_password": data["new_password"]}, context={"target_user": user}
        )
        check.is_valid(raise_exception=True)
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": _("Password updated.")})
