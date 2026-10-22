import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import Membership, Tenant


class CompanyNumberTests(TestCase):
    def test_numbers_are_mandatory_unique_at_least_five_digits_and_stable(self):
        a = Tenant.objects.create(slug="number-a", name="A")
        b = Tenant.objects.create(slug="number-b", name="B")
        self.assertGreaterEqual(a.company_id, 10000)
        self.assertNotEqual(a.company_id, b.company_id)
        number = a.company_id
        a.name = "Renamed"
        a.save()
        a.refresh_from_db()
        self.assertEqual(a.company_id, number)
        for value in [None, 9999, b.company_id]:
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                Tenant.objects.filter(pk=a.pk).update(company_id=value)

    def test_numeric_navigation_and_authorized_legacy_redirect(self):
        tenant = Tenant.objects.create(slug="number-url", name="Number URL")
        other = Tenant.objects.create(slug="number-other", name="Private company")
        user = get_user_model().objects.create_user("number-owner")
        Membership.objects.create(user=user, tenant=tenant, role="owner")
        self.client.force_login(user)
        url = reverse("company", args=[tenant.company_id])
        self.assertEqual(url, f"/companies/{tenant.company_id}/")
        self.assertContains(self.client.get(url), f"COMPANY ID {tenant.company_id}")
        self.assertContains(self.client.get(reverse("dashboard")), url)
        response = self.client.get(reverse("company-legacy", args=[tenant.pk]), {"page": 2})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], url + "?page=2")
        self.assertEqual(self.client.get(reverse("company", args=[other.company_id])).status_code, 403)
        self.assertEqual(self.client.get(reverse("company-legacy", args=[other.pk])).status_code, 403)
        self.assertEqual(self.client.get("/companies/9999/").status_code, 404)


class CompanyNumberMigrationTests(TransactionTestCase):
    def test_backfill_preserves_existing_uuid_and_membership(self):
        before = [("core", "0003_radius_authorization")]
        after = [("core", "0006_subscriber_subscriber_tenant_expiry_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            OldTenant = old_apps.get_model("core", "Tenant")
            OldMembership = old_apps.get_model("core", "Membership")
            user = get_user_model().objects.create_user("migration-owner")
            identifiers = [uuid.uuid4(), uuid.uuid4()]
            for index, identifier in enumerate(identifiers):
                tenant = OldTenant.objects.create(id=identifier, slug=f"existing-{index}", name=f"Existing {index}")
                OldMembership.objects.create(tenant=tenant, user_id=user.pk, role="owner")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(after)
        tenants = list(Tenant.objects.filter(pk__in=identifiers))
        self.assertEqual(len(tenants), 2)
        self.assertEqual(len({tenant.company_id for tenant in tenants}), 2)
        self.assertTrue(all(tenant.company_id >= 10000 for tenant in tenants))
        self.assertEqual(Membership.objects.filter(user=user, tenant_id__in=identifiers).count(), 2)
        created = Tenant.objects.create(slug="after-backfill", name="After backfill")
        self.assertNotIn(created.company_id, {tenant.company_id for tenant in tenants})


class ConcurrentCompanyNumberTests(TransactionTestCase):
    @skipUnless(connection.vendor == "mysql", "Concurrent issuance uses MariaDB auto-increment")
    def test_concurrent_company_creation_issues_distinct_numbers(self):
        def create(index):
            try:
                return Tenant.objects.create(slug=f"concurrent-{index}", name=f"Concurrent {index}").company_id
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as pool:
            numbers = list(pool.map(create, range(12)))
        self.assertEqual(len(set(numbers)), 12)
        self.assertTrue(all(number >= 10000 for number in numbers))
