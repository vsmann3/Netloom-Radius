"""Prepare/run a separate synthetic HTTPS-stage fixture, never real production."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    directory = root / ".tools" / "production-staged"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "runtime.json"
    if not path.exists():
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"django_secret_key": secrets.token_urlsafe(48), "admin_password": secrets.token_urlsafe(24)}, stream)
    runtime = json.loads(path.read_text(encoding="utf-8"))
    os.environ["CAF_ISOLATED_STAGED_TEST"] = "1"
    os.environ["DJANGO_SETTINGS_MODULE"] = "netloom.staged_test_settings"
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import connection
    from core.models import Membership, Plan, Tenant
    if connection.vendor != "sqlite" or Path(connection.settings_dict["NAME"]).resolve() != directory / "radius-staged.sqlite3" or settings.CAF_DEMO_LOCAL_HTTP:
        raise SystemExit("Unexpected fixture database/settings; refusing preparation")
    call_command("migrate", interactive=False, verbosity=0)
    actor, created = get_user_model().objects.get_or_create(username="staged-admin", defaults={"is_staff": True})
    if created:
        actor.set_password(runtime["admin_password"])
        actor.save()
    tenant, _ = Tenant.objects.get_or_create(slug="caf-staged-test", defaults={"name": "CAF STAGED HTTPS TEST ONLY"})
    Membership.objects.get_or_create(user=actor, tenant=tenant, defaults={"role": "owner"})
    Plan.objects.get_or_create(tenant=tenant, name="HTTPS test 100Mbps 7days", defaults={"upload_kbps": 100000, "download_kbps": 100000})
    access = directory / "access.txt"
    if not access.exists():
        descriptor = os.open(access, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("ISOLATED HTTPS STAGED TEST ONLY\nURL: https://127.0.0.1:18220\nCompany ID: " + str(tenant.company_id)
                         + "\nUsername: staged-admin\nPassword: " + runtime["admin_password"] + "\n")
    print(f"Independent HTTPS-stage fixture company {tenant.company_id}; no CAF binding, token or NAS auto-enabled.")
    if not args.prepare_only:
        call_command("runserver", "127.0.0.1:18150", use_reloader=False, insecure_serving=True)


if __name__ == "__main__":
    main()
