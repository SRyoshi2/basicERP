from rest_framework import serializers

from .models import Address, Contact, ContactAuditEvent, ContactImportBatch, ContactPerson
from .services import create_contact, update_contact


class AddressSerializer(serializers.ModelSerializer):
    country_code = serializers.RegexField(r"^[A-Za-z]{2}$", default="DE")

    class Meta:
        model = Address
        fields = ("id", "kind", "label", "street", "postal_code", "city", "country_code", "is_default")
        read_only_fields = ("id",)

    def validate_country_code(self, value):
        return value.upper()


class ContactPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactPerson
        fields = (
            "id",
            "salutation",
            "title",
            "first_name",
            "last_name",
            "role",
            "email",
            "phone",
            "is_primary",
        )
        read_only_fields = ("id",)


class ContactSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    contact_persons = ContactPersonSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = (
            "id",
            "customer_number",
            "kind",
            "display_name",
            "company_name",
            "salutation",
            "title",
            "first_name",
            "last_name",
            "email",
            "phone",
            "website",
            "vat_id",
            "leitweg_id",
            "version",
            "archived_at",
            "created_at",
            "updated_at",
            "addresses",
            "contact_persons",
        )


class ContactWriteMixin(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, required=False)
    contact_persons = ContactPersonSerializer(many=True, required=False)

    class Meta:
        model = Contact
        fields = (
            "kind",
            "company_name",
            "salutation",
            "title",
            "first_name",
            "last_name",
            "email",
            "phone",
            "website",
            "vat_id",
            "leitweg_id",
            "addresses",
            "contact_persons",
        )

    def to_representation(self, instance):
        return ContactSerializer(instance, context=self.context).data

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        company_name = attrs.get("company_name", getattr(self.instance, "company_name", ""))
        first_name = attrs.get("first_name", getattr(self.instance, "first_name", ""))
        last_name = attrs.get("last_name", getattr(self.instance, "last_name", ""))
        errors = {}
        if kind == Contact.Kind.ORGANIZATION and not company_name.strip():
            errors["company_name"] = ["Für Firmen ist der Firmenname erforderlich."]
        if kind == Contact.Kind.PERSON:
            if not first_name.strip():
                errors["first_name"] = ["Für Personen ist der Vorname erforderlich."]
            if not last_name.strip():
                errors["last_name"] = ["Für Personen ist der Nachname erforderlich."]
            people = attrs.get("contact_persons")
            if people is None and self.instance is not None:
                people = list(self.instance.contact_persons.all())
            if people:
                errors["contact_persons"] = ["Ansprechpartner können nur Firmen zugeordnet werden."]

        default_kinds = [item["kind"] for item in attrs.get("addresses", []) if item.get("is_default")]
        if len(default_kinds) != len(set(default_kinds)):
            errors["addresses"] = ["Pro Adresstyp ist nur eine Standardadresse erlaubt."]
        primary_people = sum(1 for item in attrs.get("contact_persons", []) if item.get("is_primary"))
        if primary_people > 1:
            errors["contact_persons"] = ["Es ist nur ein primärer Ansprechpartner erlaubt."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ContactCreateSerializer(ContactWriteMixin):
    def create(self, validated_data):
        return create_contact(validated_data, self.context["request"].user)


class ContactUpdateSerializer(ContactWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(ContactWriteMixin.Meta):
        fields = (*ContactWriteMixin.Meta.fields, "version")

    def update(self, instance, validated_data):
        return update_contact(instance.pk, validated_data, self.context["request"].user)


class ContactAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ContactAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")

    def get_actor(self, obj) -> str | None:
        return obj.actor.username if obj.actor else None


class ContactImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ContactImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactImportBatch
        fields = (
            "id",
            "source_name",
            "source_hash",
            "status",
            "rows",
            "total_count",
            "valid_count",
            "error_count",
            "created_count",
            "result",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields
