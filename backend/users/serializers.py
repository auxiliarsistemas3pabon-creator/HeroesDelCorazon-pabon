from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .areas import is_removed_area
from .models import User


def _normalize_text(value: str) -> str:
    """Colapsa espacios repetidos/extremos para evitar duplicados visuales (areas, nombres)."""
    return " ".join(value.split()).strip()


def _normalize_username(value: str) -> str:
    return value.strip()


class UserSerializer(serializers.ModelSerializer[User]):
    """Representacion publica de un usuario. role es de solo lectura: nadie se asigna rol desde la API."""
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "role",
            "area",
            "position",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "role", "date_joined", "last_login")


class AuthenticatedUserSerializer(UserSerializer):
    """Usuario autenticado (login/me): anade password_change_required para que el frontend redirija al cambio de clave."""
    password_change_required = serializers.BooleanField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, "password_change_required")


class RegisterSerializer(serializers.ModelSerializer[User]):
    """Auto-registro publico. No expone role: create_user lo deja siempre como collaborator."""
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "area",
            "position",
            "first_name",
            "last_name",
            "password",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login")
        extra_kwargs = {
            "area": {"required": True, "allow_blank": False},
            "position": {"required": True, "allow_blank": False},
        }

    def validate_username(self, value: str) -> str:
        normalized = _normalize_username(value)
        if not normalized:
            raise serializers.ValidationError(_("The username cannot be empty."))
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError(_("A user with this username already exists."))
        return normalized

    def validate_first_name(self, value: str) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise serializers.ValidationError(_("The first name cannot be empty."))
        return normalized

    def validate_last_name(self, value: str) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise serializers.ValidationError(_("The last name cannot be empty."))
        return normalized

    def validate_area(self, value: str) -> str:
        normalized = _normalize_text(value)
        if is_removed_area(normalized):
            raise serializers.ValidationError(_("The area 'Sistema' is no longer available. Use 'Sistemas'."))
        return normalized

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class PasswordChangeSerializer(serializers.Serializer):
    """Cambio de clave. Requiere target_user (y request) en el contexto.

        current_password solo se exige cuando quien cambia es el mismo usuario; el flujo de
        recuperacion por email lo reutiliza sin ella solo para validar la nueva clave.
        """
    current_password = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        target = self.context.get("target_user")
        try:
            validate_password(value, user=target)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        target = self.context.get("target_user")
        caller = getattr(request, "user", None)

        is_self = caller is not None and target is not None and caller.pk == target.pk

        if is_self:
            current = attrs.get("current_password")
            if not current:
                raise serializers.ValidationError(
                    {"current_password": _("This field is required to change your password.")}
                )
            if not target.check_password(current):
                raise serializers.ValidationError(
                    {"current_password": _("The current password is incorrect.")}
                )

        return attrs


class LoginSerializer(serializers.Serializer):
    """Credenciales de login. trim_whitespace=False para no alterar contrasenas con espacios."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
