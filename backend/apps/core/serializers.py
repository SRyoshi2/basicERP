from django.contrib.auth import password_validation
from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    is_staff = serializers.BooleanField()
    must_change_password = serializers.BooleanField()


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class CsrfTokenSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()  # noqa: N815 - public API contract


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Das aktuelle Passwort ist falsch.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value
