import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.caf_catalog import issue_token, publish_plan
from core.models import CAFCompanyBinding, CAFFranchiseBinding, CAFServiceToken, Membership, Plan, Tenant


def protected_json(path, value):
    # All files contain synthetic-demo secrets only and remain outside Git.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


class Command(BaseCommand):
    help = "Seed ONLY the independent SQLite localhost integration demo."

    def add_arguments(self, parser):
        parser.add_argument("--caf-company-id", required=True)
        parser.add_argument("--caf-franchise-id", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        directory = settings.BASE_DIR / ".tools" / "integration-demo"
        if connection.vendor != "sqlite" or not getattr(settings, "CAF_DEMO_LOCAL_HTTP", False) or Path(connection.settings_dict["NAME"]).resolve() != (directory / "radius-demo.sqlite3").resolve():
            raise CommandError("This command is restricted to the isolated laptop demo database")
        runtime = json.loads((directory / "runtime.json").read_text())
        user, created = get_user_model().objects.get_or_create(username="demo-admin", defaults={"is_staff": True, "is_superuser": True, "is_active": True})
        if created:
            user.set_password(runtime["admin_password"])
            user.save()
        tenant, _ = Tenant.objects.get_or_create(slug="caf-integration-demo", defaults={"name": "Infolink - CAF integration DEMO"})
        Membership.objects.get_or_create(tenant=tenant, user=user, defaults={"role": "owner"})
        binding, _ = CAFCompanyBinding.objects.get_or_create(source="caf-portal-demo", caf_company_id=options["caf_company_id"], defaults={"tenant": tenant})
        if binding.tenant_id != tenant.pk:
            raise CommandError("Demo company binding mismatch")
        franchise, _ = CAFFranchiseBinding.objects.get_or_create(company=binding, caf_franchise_id=options["caf_franchise_id"], defaults={"name": "Demo franchise"})
        plans = []
        for name, rate, seconds in [("Demo 100 Mbps - 7 days", 100000, 604800), ("Demo 300 Mbps - 30 days", 300000, 2592000)]:
            plan, _ = Plan.objects.get_or_create(tenant=tenant, name=name, defaults={"upload_kbps": rate, "download_kbps": rate})
            publication = publish_plan(actor=user, plan_id=plan.pk, duration_seconds=seconds)
            plans.append({"plan_id": str(plan.pk), "version": publication.version, "name": plan.name})
        config_file = directory / "connection.json"
        config = json.loads(config_file.read_text()) if config_file.exists() else {}
        existing = CAFServiceToken.objects.filter(pk=config.get("token_id"), binding=binding, active=True, expires_at__gt=timezone.now()).first() if config.get("token_id") else None
        if not existing:
            token, raw = issue_token(binding, expires_at=timezone.now() + timedelta(days=7), plans_read=True)
            CAFServiceToken.objects.filter(pk=token.pk).update(reservations_write=True, provisionings_write=True, receipts_read=True)
        else:
            token, raw = existing, config["token"]
        protected_json(config_file, {"radius_base_url": "http://127.0.0.1:18120", "source_id": binding.source,
            "radius_company_id": str(tenant.company_id), "radius_franchise_id": str(franchise.franchise_id),
            "caf_company_id": binding.caf_company_id, "caf_franchise_id": franchise.caf_franchise_id,
            "token_id": str(token.pk), "token": raw, "plans": plans})
        access = directory / "access.txt"
        descriptor = os.open(access, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("Synthetic localhost Radius demo only\nURL: http://127.0.0.1:18120\nUsername: demo-admin\nPassword: " + runtime["admin_password"] + "\n")
        self.stdout.write(f"Demo ready: company {tenant.company_id}; 2 published plans; no NAS or customer created. Connection and login files saved privately.")
