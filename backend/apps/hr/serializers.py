from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AbsenceRequest, AbsenceRequestAuditEvent, LeaveEntitlement, count_weekdays
from .services import create_absence, set_leave_entitlement, update_absence


class AbsenceRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    working_days = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AbsenceRequest
        fields = (
            "id", "employee", "employee_name", "kind", "kind_label", "start_date", "end_date",
            "working_days", "note", "status", "status_label", "decision_note", "reviewed_by",
            "reviewed_by_name", "reviewed_at", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "employee", "status", "decision_note", "reviewed_by", "reviewed_at",
            "version", "created_at", "updated_at",
        )

    def get_employee_name(self, obj) -> str:
        return obj.employee.get_full_name().strip() or obj.employee.username

    def get_reviewed_by_name(self, obj) -> str | None:
        if not obj.reviewed_by:
            return None
        return obj.reviewed_by.get_full_name().strip() or obj.reviewed_by.username


class AbsenceWriteMixin(serializers.ModelSerializer):
    class Meta:
        model = AbsenceRequest
        fields = ("kind", "start_date", "end_date", "note")

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        errors = {}
        if start_date and end_date and end_date < start_date:
            errors["end_date"] = "Das Enddatum darf nicht vor dem Startdatum liegen."
        elif start_date and end_date and count_weekdays(start_date, end_date) == 0:
            errors["end_date"] = "Der Zeitraum muss mindestens einen Arbeitstag enthalten."
        if (
            kind == AbsenceRequest.Kind.VACATION and start_date and end_date
            and start_date.year != end_date.year
        ):
            errors["end_date"] = "Urlaubsanträge müssen innerhalb eines Kalenderjahres liegen."
        if self.instance and self.instance.status != AbsenceRequest.Status.REQUESTED:
            errors["absence_request"] = "Nur beantragte Abwesenheiten können bearbeitet werden."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        return AbsenceRequestSerializer(instance, context=self.context).data


class AbsenceCreateSerializer(AbsenceWriteMixin):
    def create(self, validated_data):
        try:
            return create_absence(validated_data, self.context["request"].user)
        except ValueError as error:
            raise serializers.ValidationError({"period": str(error)}) from error


class AbsenceUpdateSerializer(AbsenceWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(AbsenceWriteMixin.Meta):
        fields = (*AbsenceWriteMixin.Meta.fields, "version")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "version" not in attrs:
            raise serializers.ValidationError({"version": "Dieses Feld ist erforderlich."})
        return attrs

    def update(self, instance, validated_data):
        try:
            return update_absence(instance.pk, validated_data, self.context["request"].user)
        except ValueError as error:
            raise serializers.ValidationError({"period": str(error)}) from error


class AbsenceReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=(AbsenceRequest.Status.APPROVED, AbsenceRequest.Status.REJECTED)
    )
    decision_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AbsenceRequestAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AbsenceRequestAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None


class LeaveBalanceSerializer(serializers.Serializer):
    employee = serializers.IntegerField()
    year = serializers.IntegerField()
    entitlement_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    carryover_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    approved_days = serializers.DecimalField(max_digits=6, decimal_places=2)
    pending_days = serializers.DecimalField(max_digits=6, decimal_places=2)
    remaining_days = serializers.DecimalField(max_digits=6, decimal_places=2)
    version = serializers.IntegerField(allow_null=True)


class LeaveEntitlementSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveEntitlement
        fields = (
            "employee", "employee_name", "year", "entitlement_days", "carryover_days",
            "version", "updated_at",
        )

    def get_employee_name(self, obj) -> str:
        return obj.employee.get_full_name().strip() or obj.employee.username


class LeaveEntitlementWriteSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_active=True)
    )
    year = serializers.IntegerField(min_value=2000, max_value=2200)
    entitlement_days = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0")
    )
    carryover_days = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    version = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def create(self, validated_data):
        return set_leave_entitlement(
            actor=self.context["request"].user,
            **validated_data,
        )

    def to_representation(self, instance):
        return LeaveEntitlementSerializer(instance, context=self.context).data
