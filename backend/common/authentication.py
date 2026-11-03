from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    """Validates the CSRF token (double cookie) on cookie-authenticated requests."""
    check = CsrfViewMiddleware(lambda r: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


# CSRF solo se valida en la rama de cookie; con header Authorization el navegador no adjunta credenciales solo.
class CookieJWTAuthentication(JWTAuthentication):
    """Accepts the Authorization header and, if missing, the access token from an httpOnly cookie."""

    def authenticate(self, request):
        if self.get_header(request) is not None:
            result = super().authenticate(request)
            if result is not None:
                self._enforce_password_change(request, result[0])
            return result

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        enforce_csrf(request)
        user = self.get_user(validated_token)
        self._enforce_password_change(request, user)
        return user, validated_token

    @staticmethod
    def _enforce_password_change(request, user):
        """Bloquea la API a quien tiene clave temporal, salvo consultar su perfil y cambiar la clave.

            allowed_views son nombres de url (users/urls.py); si se renombran, hay que actualizarlos aqui.
            """
        allowed_views = {"me", "password-change"}
        view_name = getattr(getattr(request, "resolver_match", None), "url_name", None)
        if user.password_change_required and view_name not in allowed_views:
            raise exceptions.PermissionDenied(
                "Change your temporary password before continuing."
            )
