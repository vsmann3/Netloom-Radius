import json
import os
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import NAS, Plan, Subscriber, Tenant


class Command(BaseCommand):
    help = "Populate a disposable, empty RADIUS integration database only."

    @transaction.atomic
    def handle(self, *args, **options):
        if os.environ.get("NETLOOM_INTEGRATION") != "1" or Tenant.objects.exists():
            raise CommandError("Requires an empty disposable integration database")
        data = json.loads(Path("/run/secrets/radius_integration_data").read_text())
        now = timezone.now()
        for slug, ip, password, upload, download in (
            ("integration-a", "127.0.0.2", data["password_a"], 10000, 20000),
            ("integration-b", "127.0.0.3", data["password_b"], 30000, 50000),
            ("integration-inactive", "127.0.0.6", data["password_a"], 1000, 1000),
        ):
            tenant = Tenant.objects.create(slug=slug, name=slug, active=slug != "integration-inactive")
            plan = Plan.objects.create(tenant=tenant, name="Integration", upload_kbps=upload, download_kbps=download)
            NAS.objects.create(tenant=tenant, name=slug, source_ip=ip, secret_ref=slug)
            hashed = make_password(password, hasher="pbkdf2_sha256")
            Subscriber.objects.create(tenant=tenant, plan=plan, username="same-user", password_hash=hashed, expires_at=now + timedelta(hours=1))
            if slug == "integration-a":
                NAS.objects.create(tenant=tenant, name="Disabled", source_ip="127.0.0.5", secret_ref="disabled", enabled=False)
                for username, status, expiry, credential in (
                    ("suspended", "suspended", now + timedelta(hours=1), hashed),
                    ("expired", "active", now - timedelta(seconds=1), hashed),
                    ("unusable", "active", now + timedelta(hours=1), make_password(None)),
                    ("unsupported-hash", "active", now + timedelta(hours=1), "md5$unusable$00000000000000000000000000000000"),
                ):
                    Subscriber.objects.create(tenant=tenant, plan=plan, username=username, status=status, expires_at=expiry, password_hash=credential)
        self.stdout.write("Disposable RADIUS fixtures created; no credentials printed.")
