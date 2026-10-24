from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from rest_framework import serializers

from .models import ServiceEntry, ServiceEntryAuditEvent, TimeEntry, TimeEntryAuditEvent
from .services import (
    create_service_entry, create_time_entry, resolve_catalog_price, update_service_entry,
    update_time_entry,
)


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


class ServiceEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    project_number = serializers.CharField(source="project.project_number", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    work_package_title = serializers.CharField(source="work_package.title", read_only=True)
    unit_label = serializers.SerializerMethodField()
    total_net = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    billing_status_label = serializers.CharField(source="get_billing_status_display", read_only=True)

    class Meta:
        model = ServiceEntry
        fields = (
            "id", "employee", "employee_name", "project", "project_number", "project_name",
            "work_package", "work_package_title", "catalog_item", "service_date", "quantity",
            "description", "billable", "billing_status", "billing_status_label",
            "catalog_item_number_snapshot", "catalog_item_name_snapshot", "unit_snapshot",
            "unit_label", "unit_price_snapshot", "tax_rate_snapshot", "total_net", "version",
            "archived_at", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "employee", "billing_status", "catalog_item_number_snapshot",
            "catalog_item_name_snapshot", "unit_snapshot", "unit_price_snapshot",
            "tax_rate_snapshot", "version", "archived_at", "created_at", "updated_at",
        )

    def get_employee_name(self, obj) -> str:
        return obj.employee.get_full_name().strip() or obj.employee.username

    def get_unit_label(self, obj) -> str:
        return dict(obj.catalog_item.Unit.choices).get(obj.unit_snapshot, obj.unit_snapshot)


class ServiceEntryWriteMixin(serializers.ModelSerializer):
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )

    class Meta:
        model = ServiceEntry
        fields = (
            "project", "work_package", "catalog_item", "service_date", "quantity",
            "description", "billable",
        )

    def to_representation(self, instance):
        return ServiceEntrySerializer(instance, context=self.context).data

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        work_package = attrs.get("work_package", getattr(self.instance, "work_package", None))
        catalog_item = attrs.get("catalog_item", getattr(self.instance, "catalog_item", None))
        service_date = attrs.get("service_date", getattr(self.instance, "service_date", None))
        errors = {}
        if project and project.archived_at is not None:
            errors["project"] = "Für archivierte Projekte können keine Leistungen erfasst werden."
        if work_package and work_package.archived_at is not None:
            errors["work_package"] = "Für archivierte Arbeitspakete können keine Leistungen erfasst werden."
        elif project and work_package and work_package.project_id != project.id:
            errors["work_package"] = "Das Arbeitspaket gehört nicht zum gewählten Projekt."
        if catalog_item and catalog_item.archived_at is not None:
            errors["catalog_item"] = "Archivierte Katalogleistungen können nicht erfasst werden."
        elif catalog_item and catalog_item.kind != "service":
            errors["catalog_item"] = "Es können nur Katalogeinträge vom Typ Leistung erfasst werden."
        elif catalog_item and service_date and resolve_catalog_price(catalog_item, service_date) is None:
            errors["catalog_item"] = "Für das Leistungsdatum ist kein gültiger Katalogpreis vorhanden."
        if self.instance and self.instance.archived_at is not None:
            errors["service_entry"] = "Archivierte Leistungseinträge sind unveränderbar."
        if self.instance and self.instance.billing_status == ServiceEntry.BillingStatus.BILLED:
            errors["service_entry"] = "Abgerechnete Leistungseinträge sind unveränderbar."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ServiceEntryCreateSerializer(ServiceEntryWriteMixin):
    def create(self, validated_data):
        return create_service_entry(validated_data, self.context["request"].user)


class ServiceEntryUpdateSerializer(ServiceEntryWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(ServiceEntryWriteMixin.Meta):
        fields = (*ServiceEntryWriteMixin.Meta.fields, "version")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "version" not in attrs:
            raise serializers.ValidationError({"version": "Dieses Feld ist erforderlich."})
        return attrs

    def update(self, instance, validated_data):
        return update_service_entry(instance.pk, validated_data, self.context["request"].user)


class ServiceEntryAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ServiceEntryAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None


class ProjectTimeSummarySerializer(serializers.Serializer):
    entry_count = serializers.IntegerField()
    actual_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    billable_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    unbilled_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    non_billable_hours = serializers.DecimalField(max_digits=12, decimal_places=2)
    service_entry_count = serializers.IntegerField()
    service_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    unbilled_service_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    actual_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    unbilled_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_budget_hours = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    remaining_budget_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )


class TimeReportFilterSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    project = serializers.UUIDField(required=False)
    employee = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        today = timezone.localdate()
        date_from = attrs.get("date_from", today.replace(day=1))
        date_to = attrs.get("date_to", today)
        if date_to < date_from:
            raise serializers.ValidationError({"date_to": "Das Enddatum darf nicht vor dem Startdatum liegen."})
        if date_to - date_from > timedelta(days=365):
            raise serializers.ValidationError({"date_to": "Der Berichtszeitraum darf höchstens 366 Tage umfassen."})
        attrs["date_from"] = date_from
        attrs["date_to"] = date_to
        return attrs


class TimeReportSummarySerializer(serializers.Serializer):
    time_entry_count = serializers.IntegerField()
    total_hours = serializers.DecimalField(max_digits=14, decimal_places=2)
    billable_hours = serializers.DecimalField(max_digits=14, decimal_places=2)
    time_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    service_entry_count = serializers.IntegerField()
    service_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    service_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2)


class TimeReportRowSerializer(serializers.Serializer):
    entry_type = serializers.ChoiceField(choices=("time", "service"))
    date = serializers.DateField()
    employee_name = serializers.CharField()
    project_number = serializers.CharField()
    project_name = serializers.CharField()
    work_package_title = serializers.CharField()
    description = serializers.CharField()
    hours = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, allow_null=True)
    unit = serializers.CharField()
    billable = serializers.BooleanField()
    net_value = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    billing_status = serializers.CharField()


class TimeReportSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    summary = TimeReportSummarySerializer()
    rows = TimeReportRowSerializer(many=True)
