from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers

from .models import CompanyProfile


class UserSerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.ChoiceField(choices=("admin", "employee"))
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


class CompanyProfileSerializer(serializers.ModelSerializer):
    country_code = serializers.RegexField(r"^[A-Za-z]{2}$")
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = CompanyProfile
        fields = (
            "name",
            "legal_name",
            "street",
            "postal_code",
            "city",
            "country_code",
            "vat_id",
            "tax_number",
            "email",
            "phone",
            "website",
            "logo",
            "logo_url",
            "updated_at",
        )
        read_only_fields = ("logo_url", "updated_at")
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def get_logo_url(self, obj) -> str | None:
        return obj.logo.url if obj.logo else None

    def validate_country_code(self, value):
        return value.upper()

    def update(self, instance, validated_data):
        old_logo_name = instance.logo.name
        instance = super().update(instance, validated_data)
        if old_logo_name and old_logo_name != instance.logo.name:
            storage = instance.logo.storage
            transaction.on_commit(lambda: storage.delete(old_logo_name))
        return instance


class ApiErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.JSONField(required=False)


class ApiErrorResponseSerializer(serializers.Serializer):
    error = ApiErrorSerializer()
