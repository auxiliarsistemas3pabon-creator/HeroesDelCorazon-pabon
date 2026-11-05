import json
import logging
from datetime import UTC, datetime


class AuditJSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            **getattr(record, "audit_event", {}),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def record_event(
    *,
    action,
    actor=None,
    outcome="success",
    request=None,
    status_code=None,
    resource_id=None,
    metadata=None,
):
    user = getattr(request, "user", None) if request is not None else actor
    event = {
        "action": action,
        "outcome": outcome,
        "actor_id": user.pk if getattr(user, "is_authenticated", False) else None,
        "actor_role": getattr(user, "role", None) if getattr(user, "is_authenticated", False) else None,
    }

    if request is not None:
        resolver_match = getattr(request, "resolver_match", None)
        event.update({
            "method": request.method,
            "path": request.path,
            "status_code": status_code,
            "endpoint": getattr(resolver_match, "url_name", None),
            "remote_addr": request.META.get("REMOTE_ADDR"),
        })
    if resource_id is not None:
        event["resource_id"] = resource_id
    if metadata:
        event["metadata"] = metadata

    logging.getLogger("audit").info(action, extra={"audit_event": event})
