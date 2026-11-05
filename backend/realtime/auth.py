from http.cookies import CookieError, SimpleCookie

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def _user_for_token(raw_token):
    try:
        authentication = JWTAuthentication()
        token = authentication.get_validated_token(raw_token)
        user = authentication.get_user(token)
        expires_at = token["exp"]
    except (AuthenticationFailed, TokenError):
        return AnonymousUser(), None
    return (user, expires_at) if user.is_active else (AnonymousUser(), None)


class JwtCookieAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get(b"cookie", b"").decode("latin1"))
        except CookieError:
            cookie = SimpleCookie()
        morsel = cookie.get(settings.AUTH_COOKIE_ACCESS_NAME)
        scope = dict(scope)
        user, expires_at = await _user_for_token(morsel.value) if morsel else (AnonymousUser(), None)
        scope["user"] = user
        scope["jwt_expires_at"] = expires_at
        return await self.app(scope, receive, send)
