from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission

from users.models import User

# Permisos por rol. Cada uno exige usuario autenticado y rol exacto (no jerarquico: un superadmin no es boss).
class IsSuperAdmin(BasePermission):
    message = _("Only a superadmin can perform this action.")

    def has_permission(self,request,view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.SUPERADMIN)


class IsCollaborator(BasePermission):
    message = _("Only a collaborator can perform this action.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.COLLABORATOR)


class IsBoss(BasePermission):
    message = _("Only the area boss can perform this action.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.BOSS)


# Roles que gestionan evaluaciones: el jefe (solo las suyas) y el superadmin (todas).
MANAGER_ROLES = (User.Role.BOSS, User.Role.SUPERADMIN)


class IsBossOrSuperAdmin(BasePermission):
    message = _("Only the area boss or a superadmin can perform this action.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in MANAGER_ROLES)


def owned_by(user, field="created_by"):
    """Filtro de pertenencia: el jefe solo ve lo que creó; el superadmin no se restringe."""
    return {} if user.role == User.Role.SUPERADMIN else {field: user}
