from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import CatalogAuditEvent, CatalogItem, CatalogNumberSequence, CatalogPrice


ITEM_FIELDS = ("kind", "name", "description", "unit", "tax_rate", "tax_note")


def validate_price_periods(prices):
    ordered = sorted(prices, key=lambda price: price["valid_from"])
    for index, price in enumerate(ordered):
        if price.get("valid_until") and price["valid_until"] < price["valid_from"]:
            raise ValueError("Das Enddatum darf nicht vor dem Startdatum liegen.")
        if index:
            previous = ordered[index - 1]
            if previous.get("valid_until") is None or previous["valid_until"] >= price["valid_from"]:
                raise ValueError("Preiszeiträume dürfen sich nicht überschneiden.")


def _replace_prices(item, prices):
    item.prices.all().delete()
    CatalogPrice.objects.bulk_create(CatalogPrice(item=item, **price) for price in prices)


@transaction.atomic
def create_item(validated_data, actor):
    prices = validated_data.pop("prices")
    sequence = CatalogNumberSequence.objects.select_for_update().get(pk=1)
    item_number = f"A-{sequence.next_value:05d}"
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    item = CatalogItem.objects.create(
        item_number=item_number, created_by=actor, updated_by=actor, **validated_data
    )
    _replace_prices(item, prices)
    CatalogAuditEvent.objects.create(
        item=item,
        action=CatalogAuditEvent.Action.CREATED,
        version=item.version,
        actor=actor,
        changes={"kind": item.kind},
    )
    return item


@transaction.atomic
def update_item(item_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    prices = validated_data.pop("prices", None)
    item = CatalogItem.objects.select_for_update().get(pk=item_id)
    if item.version != expected_version:
        raise VersionConflict
    changed_fields = []
    for field in ITEM_FIELDS:
        if field in validated_data and getattr(item, field) != validated_data[field]:
            setattr(item, field, validated_data[field])
            changed_fields.append(field)
    if prices is not None:
        changed_fields.append("prices")
    item.version += 1
    item.updated_by = actor
    item.full_clean()
    item.save(update_fields=(*ITEM_FIELDS, "version", "updated_by", "updated_at"))
    if prices is not None:
        _replace_prices(item, prices)
    CatalogAuditEvent.objects.create(
        item=item,
        action=CatalogAuditEvent.Action.UPDATED,
        version=item.version,
        actor=actor,
        changes={"changed_fields": sorted(set(changed_fields))},
    )
    return item


@transaction.atomic
def archive_item(item_id, actor):
    item = CatalogItem.objects.select_for_update().get(pk=item_id)
    if item.archived_at is None:
        item.archived_at = timezone.now()
        item.version += 1
        item.updated_by = actor
        item.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        CatalogAuditEvent.objects.create(
            item=item,
            action=CatalogAuditEvent.Action.ARCHIVED,
            version=item.version,
            actor=actor,
            changes={},
        )
    return item
