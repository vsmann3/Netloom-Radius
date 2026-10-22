"""Read-only rollout diagnostics; never emits credentials or changes settings."""
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core.caf_connections import staged_ready, validate_origin
from core.caf_catalog import ByteString
from django.db.models import F
from core.models import CAFCompanyBinding, CAFPlanPublication


class Command(BaseCommand):
    help = "Check production-STAGED configuration and migrations without changing data."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int)
        parser.add_argument("--require-enabled", action="store_true")

    def handle(self, *args, **options):
        failures = []
        if getattr(settings, "CAF_DEMO_LOCAL_HTTP", False) or getattr(settings, "CAF_DEMO_AUTO_ACTIVATE", False):
            failures.append("Demo settings/activation are not a production-STAGED configuration")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Pending migrations must be reviewed/applied before rollout")
        try:
            for value in settings.CAF_FINGERPRINT_KEYS.values():
                if len(bytes.fromhex(value)) < 32:
                    raise ValueError
            if settings.CAF_FINGERPRINT_KEY_ID not in settings.CAF_FINGERPRINT_KEYS:
                raise ValueError
        except (ValueError, TypeError):
            failures.append("Fingerprint key ring/current key is invalid or unavailable")
        try:
            for value in settings.CAF_CREDENTIAL_KEYS.values():
                Fernet(value.encode("ascii"))
            if settings.CAF_CREDENTIAL_KEY_ID not in settings.CAF_CREDENTIAL_KEYS:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            failures.append("Credential key ring/current key is invalid or unavailable")
        try:
            if not settings.CAF_API_ALLOWED_ORIGINS:
                raise ValueError
            for origin in settings.CAF_API_ALLOWED_ORIGINS:
                validate_origin(origin)
        except Exception:
            failures.append("CAF backend HTTPS origin allowlist is invalid or empty")
        gates = settings.CAF_CATALOG_ENABLED and settings.CAF_PROVISIONING_ENABLED and settings.CAF_PRODUCTION_STAGED_ENABLED
        self.stdout.write("Server gates: " + ("STAGED available" if gates else "OFF or partial (no readiness claim)"))
        if options["require_enabled"] and not gates:
            failures.append("Catalog/provisioning/production-STAGED server gates are not all enabled")
        bindings = CAFCompanyBinding.objects.select_related("tenant").all()
        if options["require_enabled"] and not bindings.exists():
            failures.append("No company is configured for staged integration")
        if options["company_id"] is not None:
            bindings = bindings.filter(tenant__company_id=options["company_id"])
            if not bindings.exists():
                failures.append("Selected company has no reviewed CAF binding")
        for binding in bindings:
            ready = staged_ready(binding) and binding.active and binding.tenant.active
            publications = CAFPlanPublication.objects.alias(_name_bytes=ByteString(F("name"))).filter(
                plan__tenant=binding.tenant, active=True, _name_bytes=ByteString(F("plan__name")),
                upload_kbps=F("plan__upload_kbps"), download_kbps=F("plan__download_kbps")).count()
            self.stdout.write(f"Company {binding.tenant.company_id}: {'STAGED enabled' if ready else 'disabled/unverified'}; eligible publications {publications}")
            if options["require_enabled"] and (not ready or not publications):
                failures.append(f"Company {binding.tenant.company_id} requires verified settings, explicit enable and published plans")
        if failures:
            raise CommandError("; ".join(failures))
        self.stdout.write("Configuration checks passed; this is not deployment, live API/packet acceptance or activation authorization.")
