from rest_framework import serializers

from .models import TimeEntry, TimeEntryAuditEvent
from .services import create_time_entry, update_time_entry


class TimeEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    project_number = serializers.CharField(source="project.project_number", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    work_package_title = serializers.CharField(source="work_package.title", read_only=True)
    duration_hours = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    billable_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, allow_null=True
    )
    billing_status_label = serializers.CharField(source="get_billing_status_display", read_only=True)

    class Meta:
        model = TimeEntry
        fields = (
            "id", "employee", "employee_name", "project", "project_number", "project_name",
            "work_package", "work_package_title", "work_date", "duration_minutes",
            "duration_hours", "description", "billable", "billing_status",
            "billing_status_label", "hourly_rate_snapshot", "billable_value", "version",
            "archived_at", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "employee", "billing_status", "hourly_rate_snapshot", "version", "archived_at",
            "created_at", "updated_at",
        )

    def get_employee_name(self, obj) -> str:
        return obj.employee.get_full_name().strip() or obj.employee.username


class TimeEntryWriteMixin(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1440)

    class Meta:
        model = TimeEntry
        fields = (
            "project", "work_package", "work_date", "duration_minutes", "description", "billable",
        )

    def to_representation(self, instance):
        return TimeEntrySerializer(instance, context=self.context).data

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        work_package = attrs.get("work_package", getattr(self.instance, "work_package", None))
        if project and project.archived_at is not None:
            raise serializers.ValidationError(
                {"project": "Für archivierte Projekte können keine Zeiten erfasst werden."}
            )
        if work_package and work_package.archived_at is not None:
            raise serializers.ValidationError(
                {"work_package": "Für archivierte Arbeitspakete können keine Zeiten erfasst werden."}
            )
        if project and work_package and work_package.project_id != project.id:
            raise serializers.ValidationError(
                {"work_package": "Das Arbeitspaket gehört nicht zum gewählten Projekt."}
            )
        if self.instance and self.instance.archived_at is not None:
            raise serializers.ValidationError(
                {"time_entry": "Archivierte Zeiteinträge sind unveränderbar."}
            )
        if self.instance and self.instance.billing_status == TimeEntry.BillingStatus.BILLED:
            raise serializers.ValidationError(
                {"time_entry": "Abgerechnete Zeiteinträge sind unveränderbar."}
            )
        return attrs


class TimeEntryCreateSerializer(TimeEntryWriteMixin):
    def create(self, validated_data):
        return create_time_entry(validated_data, self.context["request"].user)


class TimeEntryUpdateSerializer(TimeEntryWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(TimeEntryWriteMixin.Meta):
        fields = (*TimeEntryWriteMixin.Meta.fields, "version")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "version" not in attrs:
            raise serializers.ValidationError({"version": "Dieses Feld ist erforderlich."})
        return attrs

    def update(self, instance, validated_data):
        return update_time_entry(instance.pk, validated_data, self.context["request"].user)


class TimeEntryAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = TimeEntryAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None


class ProjectTimeSummarySerializer(serializers.Serializer):
    entry_count = serializers.IntegerField()
    actual_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    billable_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    unbilled_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    non_billable_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    actual_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    unbilled_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_budget_hours = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    remaining_budget_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
