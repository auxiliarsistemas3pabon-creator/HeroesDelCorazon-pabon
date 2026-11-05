"""Publicación de notificaciones no sensibles en grupos Channels respaldados por Redis."""

import logging
from datetime import UTC, datetime

from asgiref.sync import async_to_sync
from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer
from django.core.exceptions import ImproperlyConfigured
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

GROUPS = {
    "managers": ("realtime.managers",),
    "collaborators": ("realtime.collaborators",),
    "all": ("realtime.managers", "realtime.collaborators"),
}


def publish_event(event_name, audience):
    """Envía un evento tipado a managers, collaborators o ambos grupos.

    El mensaje solo contiene tipo y fecha; los clientes deben volver a consultar
    la API para obtener información autorizada. Errores Redis se registran.
    """
    payload = {"type": event_name, "sent_at": datetime.now(UTC).isoformat()}
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error("Realtime event was not published: channel layer is not configured.")
            return
        for group in GROUPS[audience]:
            async_to_sync(channel_layer.group_send)(
                group,
                {"type": "realtime.event", "payload": payload},
            )
    except (ImproperlyConfigured, InvalidChannelLayerError, RedisError, OSError):
        logger.exception("Realtime event publication failed: %s", event_name)
