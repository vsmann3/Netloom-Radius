"""Offline administrative setup; not an organization onboarding endpoint."""
import os
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.caf_catalog import issue_token
from core.caf_connections import GRANTS
from core.models import AuditEvent, CAFCompanyBinding, Membership, Tenant


class Command(BaseCommand):
    help = "Bind an existing company to CAF and write a new plans:read token to a protected new file."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--company-id", required=True, type=int)
        parser.add_argument("--source", required=True)
        parser.add_argument("--caf-company-id", required=True)
        parser.add_argument("--token-file", required=True)
        parser.add_argument("--expires-days", type=int, default=30)
        parser.add_argument("--grant", action="append", choices=GRANTS, help="Repeat for explicit grants; default plans_read only")

    def handle(self, *args, **options):
        if not 1 <= options["expires_days"] <= 90:
            raise CommandError("Token expiry must be 1–90 days")
        try:
            actor = get_user_model().objects.get(username=options["actor"], is_active=True)
            if actor.get_username() != options["actor"]:
                raise CommandError("Use the exact panel username spelling")
            tenant = Tenant.objects.get(company_id=options["company_id"], active=True)
            if not Membership.objects.filter(user=actor, tenant=tenant, role=Membership.Role.OWNER).exists():
                raise CommandError("Explicit company owner membership required")
            CAFCompanyBinding._meta.get_field("source").clean(options["source"], None)
            external = options["caf_company_id"]
            if not external or external != external.strip() or len(external) > 128:
                raise CommandError("Use the exact CAF company ID (1–128 characters)")
        except (get_user_model().DoesNotExist, Tenant.DoesNotExist, ValidationError) as exc:
            raise CommandError("Invalid actor, company or source") from exc
        # Parent must exist. Never overwrite a secret or print its value.
        target = Path(options["token_file"]).absolute()
        created = False
        try:
            with transaction.atomic():
                Tenant.objects.select_for_update().get(pk=tenant.pk)
                binding, _ = CAFCompanyBinding.objects.get_or_create(
                    source=options["source"], caf_company_id=external, defaults={"tenant": tenant})
                if binding.tenant_id != tenant.pk or not binding.active:
                    raise CommandError("Binding conflicts with existing records; no remapping performed")
                grants = set(options.get("grant") or ["plans_read"])
                token, raw = issue_token(binding, expires_at=timezone.now() + timedelta(days=options["expires_days"]), plans_read="plans_read" in grants)
                for grant in GRANTS[1:]:
                    setattr(token, grant, grant in grants)
                token.save(update_fields=list(GRANTS[1:]))
                # O_EXCL also refuses an existing symlink. On Windows the parent ACL
                # must be protected separately; POSIX mode 0600 is set at creation.
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
                with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
                    handle.write(raw + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                AuditEvent.objects.create(tenant=tenant, actor=actor, action="caf.token.issue", target_id=token.pk, outcome="issued")
        except Exception as exc:
            if created:
                target.unlink(missing_ok=True)
            if isinstance(exc, CommandError):
                raise
            raise CommandError("CAF catalog setup failed; transaction rolled back and no token was printed") from exc
        self.stdout.write(f"Created company-scoped token {token.pk}; grants: {', '.join(sorted(grants))}; secret written only to the requested file.")
