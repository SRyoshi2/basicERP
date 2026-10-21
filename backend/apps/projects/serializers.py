from decimal import Decimal

from rest_framework import serializers

from .models import Project, ProjectAuditEvent
from .services import create_project, update_project


class ProjectSerializer(serializers.ModelSerializer):
    customer_number = serializers.CharField(source="customer.customer_number", read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Project
        fields = (
            "id", "project_number", "customer", "customer_number", "customer_name", "name",
            "description", "status", "status_label", "start_date", "end_date", "budget_amount",
            "budget_hours", "default_hourly_rate", "version", "archived_at", "created_at", "updated_at",
        )


class ProjectWriteMixin(serializers.ModelSerializer):
    budget_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False)
    budget_hours = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False)
    default_hourly_rate = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False)

    class Meta:
        model = Project
        fields = (
            "customer", "name", "description", "status", "start_date", "end_date",
            "budget_amount", "budget_hours", "default_hourly_rate",
        )

    def to_representation(self, instance):
        return ProjectSerializer(instance, context=self.context).data

    def validate_customer(self, value):
        if value.archived_at is not None:
            raise serializers.ValidationError("Archivierte Kontakte können keinem Projekt zugeordnet werden.")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "Das Enddatum darf nicht vor dem Startdatum liegen."})
        return attrs


class ProjectCreateSerializer(ProjectWriteMixin):
    def create(self, validated_data):
        return create_project(validated_data, self.context["request"].user)


class ProjectUpdateSerializer(ProjectWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(ProjectWriteMixin.Meta):
        fields = (*ProjectWriteMixin.Meta.fields, "version")

    def update(self, instance, validated_data):
        return update_project(instance.pk, validated_data, self.context["request"].user)


class ProjectAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ProjectAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None
