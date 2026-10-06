from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import Address, Contact, ContactAuditEvent, ContactNumberSequence, ContactPerson


CONTACT_FIELDS = (
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
)


def _replace_nested(contact, addresses=None, contact_persons=None):
    if addresses is not None:
        contact.addresses.all().delete()
        Address.objects.bulk_create(Address(contact=contact, **item) for item in addresses)
    if contact_persons is not None:
        contact.contact_persons.all().delete()
        ContactPerson.objects.bulk_create(
            ContactPerson(contact=contact, **item) for item in contact_persons
        )


@transaction.atomic
def create_contact(validated_data, actor):
    addresses = validated_data.pop("addresses", [])
    contact_persons = validated_data.pop("contact_persons", [])
    sequence = ContactNumberSequence.objects.select_for_update().get(pk=1)
    customer_number = f"K-{sequence.next_value:05d}"
    sequence.next_value += 1
    sequence.save(update_fields=["next_value"])

    contact = Contact.objects.create(
        customer_number=customer_number,
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )
    _replace_nested(contact, addresses, contact_persons)
    ContactAuditEvent.objects.create(
        contact=contact,
        action=ContactAuditEvent.Action.CREATED,
        version=contact.version,
        actor=actor,
        changes={"kind": contact.kind},
    )
    return contact


@transaction.atomic
def update_contact(contact_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    addresses = validated_data.pop("addresses", None)
    contact_persons = validated_data.pop("contact_persons", None)
    contact = Contact.objects.select_for_update().get(pk=contact_id)
    if contact.version != expected_version:
        raise VersionConflict

    changed_fields = []
    for field in CONTACT_FIELDS:
        if field in validated_data and getattr(contact, field) != validated_data[field]:
            setattr(contact, field, validated_data[field])
            changed_fields.append(field)
    if addresses is not None:
        changed_fields.append("addresses")
    if contact_persons is not None:
        changed_fields.append("contact_persons")

    contact.version += 1
    contact.updated_by = actor
    contact.full_clean()
    contact.save(update_fields=(*CONTACT_FIELDS, "version", "updated_by", "updated_at"))
    _replace_nested(contact, addresses, contact_persons)
    ContactAuditEvent.objects.create(
        contact=contact,
        action=ContactAuditEvent.Action.UPDATED,
        version=contact.version,
        actor=actor,
        changes={"changed_fields": sorted(set(changed_fields))},
    )
    return contact


@transaction.atomic
def archive_contact(contact_id, actor):
    contact = Contact.objects.select_for_update().get(pk=contact_id)
    if contact.archived_at is None:
        contact.archived_at = timezone.now()
        contact.version += 1
        contact.updated_by = actor
        contact.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        ContactAuditEvent.objects.create(
            contact=contact,
            action=ContactAuditEvent.Action.ARCHIVED,
            version=contact.version,
            actor=actor,
            changes={},
        )
    return contact
