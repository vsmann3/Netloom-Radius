from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Membership, Plan, Subscriber, Tenant


class Command(BaseCommand):
    help = "Create an idempotent lab tenant; synthetic subscribers require explicit opt-in."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", default="lab")
        parser.add_argument("--owner", help="Existing Django username to grant tenant owner membership")
        parser.add_argument("--synthetic-subscribers", type=int, default=0)
        parser.add_argument("--allow-synthetic-data", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["synthetic_subscribers"]
        if count < 0 or count > 500:
            raise CommandError("Synthetic subscriber count must be between 0 and 500")
        if count and not options["allow_synthetic_data"]:
            raise CommandError("Synthetic data requires --allow-synthetic-data")
        tenant, _ = Tenant.objects.get_or_create(slug=options["tenant"], defaults={"name": options["tenant"]})
        if options["owner"]:
            from django.contrib.auth import get_user_model

            try:
                user = get_user_model().objects.get(username=options["owner"], is_active=True)
            except get_user_model().DoesNotExist as exc:
                raise CommandError("Owner must be an existing active user") from exc
            Membership.objects.get_or_create(tenant=tenant, user=user, defaults={"role": "owner"})
        plan, _ = Plan.objects.get_or_create(tenant=tenant, name="Lab 20/50 Mbps", defaults={"upload_kbps": 20000, "download_kbps": 50000})
        for index in range(count):
            Subscriber.objects.get_or_create(tenant=tenant, username=f"synthetic-{index + 1:04}", defaults={
                # Unusable credentials by default; never provision a shared demo password.
                "password_hash": make_password(None), "plan": plan,
                "expires_at": timezone.now() + timedelta(days=30),
            })
        self.stdout.write(self.style.SUCCESS(f"Lab tenant {tenant.slug} ready; existing records preserved."))
