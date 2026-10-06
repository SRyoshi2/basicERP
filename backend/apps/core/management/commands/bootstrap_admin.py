import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Erstellt den initialen Admin, ohne einen bestehenden Account zurückzusetzen."

    def handle(self, *args, **options):
        username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
        password = os.getenv("INITIAL_ADMIN_PASSWORD")
        email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@localhost.invalid")

        if not password:
            raise CommandError("INITIAL_ADMIN_PASSWORD ist nicht gesetzt.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "role": user_model.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "must_change_password": True,
            },
        )

        if not created:
            self.stdout.write(self.style.WARNING(f"Benutzer '{username}' existiert bereits; Passwort bleibt unverändert."))
            return

        user.set_password(password)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"Initialer Admin '{username}' wurde erstellt. Passwortwechsel ist erzwungen."))
