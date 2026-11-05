"""Integración de auditoría y publicación de eventos con las vistas DRF."""

from rest_framework import status

from .logging import record_event

# Mapea (nombre de ruta, método) a (tipo de evento, audiencia WebSocket).
REALTIME_ENDPOINTS = {
    ("questions", "POST"): ("questions.submitted", "managers"),
    ("question-evaluations", "POST"): ("evaluations.updated", "all"),
    ("question-evaluation", "PATCH"): ("evaluations.updated", "all"),
    ("question-evaluation", "DELETE"): ("evaluations.updated", "all"),
    ("question-evaluation-program-create", "POST"): ("evaluations.updated", "all"),
    ("question-categories", "POST"): ("evaluations.updated", "all"),
    ("question-category", "PATCH"): ("evaluations.updated", "all"),
    ("question-category", "DELETE"): ("evaluations.updated", "all"),
    ("question-category-criteria", "POST"): ("evaluations.updated", "all"),
    ("question-criterion", "PATCH"): ("evaluations.updated", "all"),
    ("question-criterion", "DELETE"): ("evaluations.updated", "all"),
    ("question-settings", "PUT"): ("evaluations.updated", "all"),
    ("question-import", "POST"): ("evaluations.updated", "all"),
    ("question-answers-import", "POST"): ("questions.submitted", "managers"),
    ("staff-import", "POST"): ("staff.updated", "managers"),
    ("register", "POST"): ("staff.updated", "managers"),
}


class AuditLogMixin:
    """Audita solicitudes mutantes y publica los eventos realtime asociados si tienen éxito.

    No captura datos de entrada/salida. Los errores HTTP también se auditan; solo las
    respuestas exitosas generan notificaciones WebSocket.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return response

        match = getattr(request._request, "resolver_match", None)
        endpoint = getattr(match, "url_name", None) or request.path
        outcome = "success" if response.status_code < status.HTTP_400_BAD_REQUEST else "failure"
        record_event(
            action=f"{endpoint}.{request.method.lower()}",
            request=request,
            outcome=outcome,
            status_code=response.status_code,
        )

        realtime = REALTIME_ENDPOINTS.get((endpoint, request.method))
        if realtime and outcome == "success":
            from realtime.events import publish_event

            publish_event(*realtime)
        return response
