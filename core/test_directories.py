from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Membership, NAS, Plan, Subscriber, Tenant


class SubscriberDirectoryTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 22, 12, tzinfo=utc.utc)
        self.a = Tenant.objects.create(slug="directory-a", name="Directory A")
        self.b = Tenant.objects.create(slug="directory-b", name="Directory B")
        self.user = get_user_model().objects.create_user("directory-owner")
        Membership.objects.create(user=self.user, tenant=self.a, role="owner")
        self.plan = Plan.objects.create(tenant=self.a, name="Basic", upload_kbps=1000, download_kbps=2000)
        self.other_plan = Plan.objects.create(tenant=self.a, name="Premium", upload_kbps=2000, download_kbps=5000)
        self.foreign_plan = Plan.objects.create(tenant=self.b, name="Private foreign plan", upload_kbps=1000, download_kbps=2000)
        self.alpha = Subscriber.objects.create(tenant=self.a, username="Alpha-user", password_hash="!", plan=self.plan, expires_at=self.now + timedelta(days=2))
        self.beta = Subscriber.objects.create(tenant=self.a, username="Beta-user", password_hash="!", plan=self.other_plan, status="suspended", expires_at=self.now - timedelta(days=1))
        self.foreign = Subscriber.objects.create(tenant=self.b, username="Foreign-user", password_hash="!", plan=self.foreign_plan, expires_at=self.now)
        Subscriber.objects.filter(pk=self.alpha.pk).update(created_at=datetime(2026, 10, 1, 23, 59, tzinfo=utc.utc), last_renewed_at=datetime(2026, 10, 20, 23, 59, tzinfo=utc.utc))
        Subscriber.objects.filter(pk=self.beta.pk).update(created_at=datetime(2026, 10, 2, tzinfo=utc.utc))
        self.url = reverse("company-users", args=[self.a.company_id])
        self.client.force_login(self.user)

    def results(self, **filters):
        with patch("core.directories.timezone.now", return_value=self.now):
            response = self.client.get(self.url, filters)
        self.assertEqual(response.status_code, 200)
        return response, [record.username for record in response.context["records"]]

    def test_dedicated_pages_and_access(self):
        overview = self.client.get(reverse("company", args=[self.a.company_id]))
        self.assertNotContains(overview, "Subscriber directory")
        self.assertNotContains(overview, "Create plan")
        for route, heading in [("company-users", "Users / Subscribers"), ("company-plans", "Speed profiles"), ("company-routers", "Network access servers")]:
            response = self.client.get(reverse(route, args=[self.a.company_id]))
            self.assertContains(response, heading)
            self.assertEqual(self.client.get(reverse(route, args=[self.b.company_id])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_identity_plan_and_state_filters(self):
        for query, expected in [({}, ["Alpha-user", "Beta-user"]),
                                ({"username": "ALPHA"}, ["Alpha-user"]),
                                ({"account_id": str(self.alpha.pk)}, ["Alpha-user"]),
                                ({"account_id": str(self.foreign.pk)}, []),
                                ({"plan": str(self.other_plan.pk)}, ["Beta-user"]),
                                ({"status": "suspended"}, ["Beta-user"]),
                                ({"validity": "expired"}, ["Beta-user"]),
                                ({"validity": "expiring", "status": "active"}, ["Alpha-user"]),
                                ({"validity": "valid"}, ["Alpha-user"])]:
            with self.subTest(query=query):
                response, names = self.results(**query)
                self.assertEqual(names, expected)
                self.assertNotContains(response, "Foreign-user")
                self.assertNotContains(response, "Private foreign plan")

    def test_inclusive_date_ranges_and_unrecorded_renewals(self):
        for query, expected in [({"created_from": "2026-10-01", "created_to": "2026-10-01"}, ["Alpha-user"]),
                                ({"expiry_from": "2026-10-24", "expiry_to": "2026-10-24"}, ["Alpha-user"]),
                                ({"renewal_from": "2026-10-20", "renewal_to": "2026-10-20"}, ["Alpha-user"]),
                                ({"renewal_record": "unrecorded"}, ["Beta-user"]),
                                ({"renewal_record": "recorded"}, ["Alpha-user"])]:
            with self.subTest(query=query):
                self.assertEqual(self.results(**query)[1], expected)

    def test_invalid_filters_show_errors_and_do_not_broaden_results(self):
        for query in [{"account_id": "bad-id"}, {"plan": str(self.foreign_plan.pk)},
                      {"expiry_from": "2026-10-24", "expiry_to": "2026-10-01"},
                      {"renewal_from": "not-a-date"}, {"status": "invalid"},
                      {"sort": "password_hash"}, {"per_page": "1000000"}]:
            with self.subTest(query=query):
                response, names = self.results(**query)
                self.assertEqual(names, [])
                self.assertTrue(response.context["filter_form"].errors)

    def test_sorting_and_pagination_keep_filters(self):
        Subscriber.objects.bulk_create([Subscriber(tenant=self.a, username=f"match-{index:02}", password_hash="!", plan=self.plan, expires_at=self.now) for index in range(30)])
        response, names = self.results(username="match-", per_page=25, sort="-username")
        self.assertEqual(len(names), 25)
        self.assertEqual(names[0], "match-29")
        self.assertContains(response, "username=match-")
        self.assertContains(response, "page=2")
        response, names = self.results(username="match-", per_page=25, sort="-username", page=2)
        self.assertEqual(len(names), 5)
        self.assertEqual(names[-1], "match-00")

    def test_read_only_directory_and_post_csrf(self):
        Membership.objects.filter(user=self.user).update(role="viewer")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Add subscriber")
        self.assertNotContains(response, 'type="submit" aria-label="Suspend')
        self.assertEqual(self.client.post(self.url, {"kind": "subscriber"}).status_code, 403)
