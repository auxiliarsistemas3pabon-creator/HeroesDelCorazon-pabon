"""ASGI entry point for HTTP and authenticated realtime events."""
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

django_application = get_asgi_application()

from realtime.auth import JwtCookieAuthMiddleware
from realtime.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_application,
    "websocket": AllowedHostsOriginValidator(
        JwtCookieAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
