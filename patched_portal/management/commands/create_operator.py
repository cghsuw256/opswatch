from getpass import getpass

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from patched_portal.ranks import RANKS
from unit_portal.approvals import seed_example_approval
from unit_portal.profiles import get_profile


class Command(BaseCommand):
    help = "Create a patched-site account with a locally entered password."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--name", required=True)
        parser.add_argument("--rank", required=True, choices=RANKS)
        parser.add_argument("--diagnostics", action="store_true")
        parser.add_argument("--portal-admin", action="store_true")

    def handle(self, *, username, name, rank, diagnostics, portal_admin, **options):
        user = get_user_model()(username=username)
        try:
            user.full_clean(exclude=["password"])
            password = getpass("Password: ")
            if password != getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")
            password_validation.validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        user.set_password(password)
        with transaction.atomic():
            user.save()
            profile = get_profile(user)
            profile.name = name
            profile.title = rank
            if portal_admin:
                profile.role = "admin"
            try:
                profile.full_clean()
            except ValidationError as error:
                raise CommandError(" ".join(error.messages)) from error
            profile.save(update_fields=["name", "title", "role"])
            seed_example_approval(user)
            if diagnostics:
                user.user_permissions.add(Permission.objects.get(
                    content_type__app_label="inventory", content_type__model="server",
                    codename="run_diagnostics",
                ))
        self.stdout.write(self.style.SUCCESS(f"Created {user.username}."))
