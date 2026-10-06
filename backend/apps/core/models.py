from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        EMPLOYEE = "employee", "Mitarbeiter"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EMPLOYEE)
    must_change_password = models.BooleanField(default=False)


def validate_logo_size(value):
    if value.size > 2 * 1024 * 1024:
        raise ValidationError("Das Logo darf höchstens 2 MB groß sein.")


class CompanyProfile(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=200, blank=True)
    legal_name = models.CharField(max_length=200, blank=True)
    street = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country_code = models.CharField(
        max_length=2,
        default="DE",
        validators=[RegexValidator(r"^[A-Z]{2}$", "Bitte einen zweistelligen ISO-Ländercode angeben.")],
    )
    vat_id = models.CharField(max_length=32, blank=True)
    tax_number = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(
        upload_to="company/logos/",
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg", "webp"]),
            validate_logo_size,
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_company_profiles",
    )

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_company_profile")]

    def save(self, *args, **kwargs):
        if self.pk not in (None, 1):
            raise ValidationError("basicERP unterstützt genau ein Firmenprofil.")
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.legal_name or "Firmenprofil"
