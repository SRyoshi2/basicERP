from decimal import Decimal

from rest_framework import serializers

from .models import Project, ProjectAuditEvent, WorkPackage, WorkPackageAuditEvent
from .services import (
    create_project, create_work_package, update_project, update_work_package,
)


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


class AssigneeOptionSerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj) -> str:
        return obj.get_full_name().strip() or obj.username


class WorkPackageSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    assignee_name = serializers.SerializerMethodField()
    resolved_hourly_rate = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True
    )
    planned_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, allow_null=True
    )

    class Meta:
        model = WorkPackage
        fields = (
            "id", "project", "title", "description", "status", "status_label", "planned_hours",
            "assignee", "assignee_name", "hourly_rate_override", "resolved_hourly_rate",
            "planned_value", "version", "archived_at", "created_at", "updated_at",
        )

    def get_assignee_name(self, obj) -> str | None:
        if not obj.assignee:
            return None
        return obj.assignee.get_full_name().strip() or obj.assignee.username


class WorkPackageWriteMixin(serializers.ModelSerializer):
    planned_hours = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    hourly_rate_override = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False
    )

    class Meta:
        model = WorkPackage
        fields = (
            "project", "title", "description", "status", "planned_hours", "assignee",
            "hourly_rate_override",
        )

    def to_representation(self, instance):
        return WorkPackageSerializer(instance, context=self.context).data

    def validate_project(self, value):
        if value.archived_at is not None:
            raise serializers.ValidationError(
                "Für archivierte Projekte können keine Arbeitspakete gepflegt werden."
            )
        return value

    def validate_assignee(self, value):
        if value is not None and not value.is_active:
            raise serializers.ValidationError("Nur aktive Benutzer können zugeordnet werden.")
        return value


class WorkPackageCreateSerializer(WorkPackageWriteMixin):
    def create(self, validated_data):
        return create_work_package(validated_data, self.context["request"].user)


class WorkPackageUpdateSerializer(WorkPackageWriteMixin):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(WorkPackageWriteMixin.Meta):
        fields = (*WorkPackageWriteMixin.Meta.fields, "version")

    def validate(self, attrs):
        if self.instance.archived_at is not None:
            raise serializers.ValidationError(
                {"work_package": "Archivierte Arbeitspakete sind unveränderbar."}
            )
        return attrs

    def update(self, instance, validated_data):
        return update_work_package(instance.pk, validated_data, self.context["request"].user)


class WorkPackageAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = WorkPackageAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None


class ProjectControllingSerializer(serializers.Serializer):
    work_package_count = serializers.IntegerField()
    planned_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    planned_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    unpriced_work_package_count = serializers.IntegerField()
    remaining_hours = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    progress_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
