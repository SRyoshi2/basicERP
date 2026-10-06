from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import CatalogAuditEvent, CatalogItem, CatalogPrice
from .services import create_item, update_item, validate_price_periods

TAX_RATE_CHOICES = (("19.00", "19 %"), ("7.00", "7 %"), ("0.00", "0 %"))


class CatalogPriceSerializer(serializers.ModelSerializer):
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))

    class Meta:
        model = CatalogPrice
        fields = ("id", "net_amount", "valid_from", "valid_until")
        read_only_fields = ("id",)


class CatalogItemSerializer(serializers.ModelSerializer):
    tax_rate = serializers.ChoiceField(choices=TAX_RATE_CHOICES)
    prices = CatalogPriceSerializer(many=True, read_only=True)
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = CatalogItem
        fields = (
            "id",
            "item_number",
            "kind",
            "name",
            "description",
            "unit",
            "tax_rate",
            "tax_note",
            "current_price",
            "prices",
            "version",
            "archived_at",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(CatalogPriceSerializer(allow_null=True))
    def get_current_price(self, instance):
        today = timezone.localdate()
        price = next(
            (
                candidate
                for candidate in instance.prices.all()
                if candidate.valid_from <= today
                and (candidate.valid_until is None or candidate.valid_until >= today)
            ),
            None,
        )
        return CatalogPriceSerializer(price).data if price else None


class CatalogWriteMixin(serializers.ModelSerializer):
    tax_rate = serializers.ChoiceField(choices=TAX_RATE_CHOICES)
    prices = CatalogPriceSerializer(many=True, required=False)

    class Meta:
        model = CatalogItem
        fields = ("kind", "name", "description", "unit", "tax_rate", "tax_note", "prices")

    def to_representation(self, instance):
        return CatalogItemSerializer(instance, context=self.context).data

    def validate_prices(self, value):
        try:
            validate_price_periods(value)
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from error
        return value

    def validate(self, attrs):
        prices = attrs.get("prices")
        if self.instance is None and not prices:
            raise serializers.ValidationError({"prices": "Mindestens ein Preis ist erforderlich."})
        return attrs


class CatalogItemCreateSerializer(CatalogWriteMixin):
    prices = CatalogPriceSerializer(many=True)

    def create(self, validated_data):
        return create_item(validated_data, self.context["request"].user)


class CatalogItemUpdateSerializer(CatalogWriteMixin):
    version = serializers.IntegerField(min_value=1, write_only=True)

    class Meta(CatalogWriteMixin.Meta):
        fields = (*CatalogWriteMixin.Meta.fields, "version")

    def update(self, instance, validated_data):
        return update_item(instance.pk, validated_data, self.context["request"].user)


class CatalogAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", allow_null=True)

    class Meta:
        model = CatalogAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")
