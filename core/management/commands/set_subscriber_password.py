import getpass

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import AuditEvent, Subscriber, Tenant
from core.services import require_membership


class Command(BaseCommand):
    help = "Set a PAP subscriber password via a hidden prompt, with tenant authorization and audit."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--actor", required=True, help="Existing operator/owner Django username")

    @transaction.atomic
    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        try:
            tenant = Tenant.objects.get(slug=options["tenant"], active=True)
            actor = get_user_model().objects.get(username=options["actor"], is_active=True)
            require_membership(actor, tenant.id, write=True)
            subscriber = Subscriber.objects.select_for_update().get(tenant=tenant, username=options["username"])
        except (Tenant.DoesNotExist, get_user_model().DoesNotExist, Subscriber.DoesNotExist) as exc:
            raise CommandError("Tenant, operator or subscriber not found") from exc
        if subscriber.username != options["username"]:
            raise CommandError("Subscriber username spelling does not match")
        password = getpass.getpass("New subscriber password: ")
        if password != getpass.getpass("Repeat password: "):
            raise CommandError("Passwords do not match")
        if not password or len(password.encode("utf-8")) > 128:
            raise CommandError("PAP passwords must contain 1 to 128 UTF-8 bytes")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        subscriber.password_hash = make_password(password, hasher="pbkdf2_sha256")
        subscriber.save(update_fields=["password_hash"])
        AuditEvent.objects.create(tenant=tenant, actor=actor, action="subscriber.password_set", target_id=subscriber.id, outcome="saved")
        self.stdout.write(self.style.SUCCESS("Subscriber PAP credential saved and audited."))
