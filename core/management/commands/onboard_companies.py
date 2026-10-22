from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import AuditEvent, Membership, Tenant


class Command(BaseCommand):
    help = "Preview or create companies and explicit owner memberships for an existing platform administrator."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Existing active panel superuser; no password is changed")
        parser.add_argument("--company", action="append", required=True, metavar="SLUG=NAME")
        parser.add_argument("--apply", action="store_true", help="Commit the reviewed onboarding; otherwise preview only")

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=options["owner"], is_active=True, is_superuser=True)
        except user_model.DoesNotExist as exc:
            raise CommandError("Owner must be an existing active platform administrator") from exc
        if owner.get_username() != options["owner"]:
            raise CommandError("Panel username spelling does not match")

        companies = []
        seen = set()
        for specification in options["company"]:
            slug, separator, name = specification.partition("=")
            name = name.strip()
            try:
                Tenant._meta.get_field("slug").clean(slug, None)
                Tenant._meta.get_field("name").clean(name, None)
            except ValidationError as exc:
                raise CommandError("Invalid company slug or name") from exc
            if not separator or slug != slug.lower() or slug in seen:
                raise CommandError("Use unique lowercase company slugs in SLUG=NAME format")
            seen.add(slug)
            companies.append((slug, name))

        # Inspect every requested company before making any changes.
        for slug, name in companies:
            existing = Tenant.objects.select_for_update().filter(slug=slug).first()
            if existing is not None:
                if existing.slug != slug or existing.name != name or not existing.active:
                    raise CommandError(f"Company {slug} conflicts with an existing record; nothing was changed")
                membership = Membership.objects.select_for_update().filter(tenant=existing, user=owner).first()
                if membership is not None and membership.role != Membership.Role.OWNER:
                    raise CommandError(f"Existing membership for {slug} is not owner; nothing was changed")
            self.stdout.write(f"{slug}: {name}; owner: {owner.get_username()}")

        if not options["apply"]:
            self.stdout.write("Preview only. Re-run with --apply to create missing companies and owner memberships.")
            return

        for slug, name in companies:
            tenant, created = Tenant.objects.get_or_create(slug=slug, defaults={"name": name})
            # Recheck after get_or_create in case another administrator created it.
            if tenant.slug != slug or tenant.name != name or not tenant.active:
                raise CommandError(f"Company {slug} changed during onboarding; nothing was committed")
            if created:
                AuditEvent.objects.create(tenant=tenant, actor=owner, action="tenant.create", target_id=tenant.pk, outcome="saved")
            membership, granted = Membership.objects.get_or_create(
                tenant=tenant, user=owner, defaults={"role": Membership.Role.OWNER},
            )
            if membership.role != Membership.Role.OWNER:
                raise CommandError(f"Membership for {slug} changed during onboarding; nothing was committed")
            if granted:
                AuditEvent.objects.create(tenant=tenant, actor=owner, action="membership.owner_grant", target_id=tenant.pk, outcome="saved")
        self.stdout.write(self.style.SUCCESS("Company onboarding complete; existing records and login credentials preserved."))
