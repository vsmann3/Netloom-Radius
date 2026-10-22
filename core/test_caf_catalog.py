from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .caf_catalog import issue_token, publish_plan
from .models import AuditEvent, CAFCompanyBinding, CAFPlanPublication, CAFServiceToken, Membership, Plan, Subscriber, Tenant


@override_settings(CAF_CATALOG_ENABLED=True)
class CAFCatalogTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="infolink", name="Infolink")
        self.other = Tenant.objects.create(slug="northnet", name="NorthNet")
        self.actor = get_user_model().objects.create_user("owner")
        Membership.objects.create(tenant=self.tenant, user=self.actor, role="owner")
        self.binding = CAFCompanyBinding.objects.create(source="caf-portal", caf_company_id="caf-company-a", tenant=self.tenant)
        self.token, self.raw = issue_token(self.binding, expires_at=timezone.now() + timedelta(days=1), plans_read=True)
        self.plan = Plan.objects.create(tenant=self.tenant, name="300 Mbps", upload_kbps=300000, download_kbps=300000)
        self.url = f"/api/integrations/ecaf/v1/companies/{self.tenant.company_id}/plans"

    def get(self, url=None, raw=None, **kwargs):
        return self.client.get(url or self.url, secure=True, HTTP_AUTHORIZATION="Bearer " + (raw or self.raw), **kwargs)

    def publish(self, plan=None, **kwargs):
        return publish_plan(actor=self.actor, plan_id=(plan or self.plan).pk, duration_seconds=kwargs.pop("duration_seconds", 2592000), **kwargs)

    def test_default_disabled_and_https_required(self):
        with override_settings(CAF_CATALOG_ENABLED=False):
            self.assertEqual(self.get().status_code, 503)
        response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer " + self.raw, HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "https_required")

    def test_staff_cookie_is_not_service_authentication(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(self.url, secure=True).status_code, 401)
        for header in ["", "Bearer browser-session-token", "Basic " + self.raw, "Bearer " + self.raw + "extra"]:
            with self.subTest(header=header[:10]):
                r = self.client.get(self.url, secure=True, HTTP_AUTHORIZATION=header)
                self.assertEqual(r.status_code, 401)
                self.assertNotIn(self.raw, r.content.decode())

    @override_settings(CAF_CATALOG_PROXY_IPS=["192.0.2.1"])
    def test_forwarded_https_requires_exact_trusted_peer(self):
        for remote, expected in [("192.0.2.1", 200), ("192.0.2.2", 400)]:
            response = self.client.get(self.url, REMOTE_ADDR=remote, HTTP_X_FORWARDED_PROTO="https",
                                       HTTP_AUTHORIZATION="Bearer " + self.raw)
            self.assertEqual(response.status_code, expected)

    def test_secret_is_hashed_and_wrong_secret_is_denied(self):
        self.assertNotIn(self.raw.split(".")[1], self.token.secret_digest)
        self.assertEqual(len(self.token.secret_digest), 64)
        self.assertEqual(self.get(raw=self.raw[:-1] + ("a" if self.raw[-1] != "a" else "b")).status_code, 401)

    def test_revocation_expiry_and_inactive_binding_tenant(self):
        for field, value in [("active", False), ("expires_at", timezone.now() - timedelta(seconds=1))]:
            with self.subTest(field=field):
                CAFServiceToken.objects.filter(pk=self.token.pk).update(**{field: value})
                self.assertEqual(self.get().status_code, 401)
                CAFServiceToken.objects.filter(pk=self.token.pk).update(active=True, expires_at=timezone.now() + timedelta(days=1))
        self.binding.active = False
        self.binding.save()
        self.assertEqual(self.get().status_code, 401)
        self.binding.active = True
        self.binding.save()
        self.tenant.active = False
        self.tenant.save()
        self.assertEqual(self.get().status_code, 401)

    def test_grant_and_company_scope_do_not_expand_from_query(self):
        CAFServiceToken.objects.filter(pk=self.token.pk).update(plans_read=False)
        self.assertEqual(self.get().status_code, 403)
        CAFServiceToken.objects.filter(pk=self.token.pk).update(plans_read=True)
        self.assertEqual(self.get(url=self.url.replace(str(self.tenant.company_id), str(self.other.company_id))).status_code, 404)
        self.assertEqual(self.get(url=self.url + "?company_id=" + str(self.other.company_id)).status_code, 400)

    def test_only_published_validity_is_exposed_and_no_activation(self):
        self.assertEqual(self.get().json()["items"], [])
        self.publish()
        other_plan = Plan.objects.create(tenant=self.other, name="Private", upload_kbps=1, download_kbps=1)
        CAFPlanPublication.objects.create(plan=other_plan, name="Private", upload_kbps=1, download_kbps=1, duration_seconds=1)
        r = self.get()
        self.assertEqual(r.status_code, 200)
        item, = r.json()["items"]
        self.assertEqual(item, {"plan_id": str(self.plan.pk), "radius_company_id": str(self.tenant.company_id),
                                "name": "300 Mbps", "version": 1, "active": True,
                                "download_kbps": 300000, "upload_kbps": 300000,
                                "validity": {"duration_seconds": 2592000, "starts_at": "activation"}})
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertFalse(Subscriber.objects.exists())

    def test_changed_plan_disappears_until_republished_and_version_advances(self):
        self.publish()
        # MariaDB's default text collation otherwise misses case-only changes.
        self.plan.name = "300 mbps"
        self.plan.save()
        self.assertEqual(self.get().json()["items"], [])
        self.plan.name = "300 Mbps"
        self.plan.download_kbps = 400000
        self.plan.save()
        self.assertEqual(self.get().json()["items"], [])
        self.assertEqual(self.publish().version, 2)
        self.assertEqual(self.publish().version, 2)
        self.assertEqual(self.get().json()["items"][0]["download_kbps"], 400000)
        self.assertEqual(self.publish(active=False).version, 3)
        self.assertEqual(self.get().json()["items"], [])

    def test_publication_requires_membership_valid_duration_and_atomic_audit(self):
        Membership.objects.filter(user=self.actor).update(role="viewer")
        with self.assertRaises(PermissionDenied):
            self.publish()
        Membership.objects.filter(user=self.actor).update(role="owner")
        for duration in [0, -1, True, 1.5, 4294967296]:
            with self.assertRaises(ValueError):
                self.publish(duration_seconds=duration)
        with patch("core.caf_catalog.AuditEvent.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.publish()
        self.assertFalse(CAFPlanPublication.objects.exists())

    def test_pagination_and_cursor_binding_tamper_expiry(self):
        for i in range(3):
            p = Plan.objects.create(tenant=self.tenant, name=f"Plan{i}", upload_kbps=1, download_kbps=1)
            self.publish(p)
        first = self.get(url=self.url + "?limit=2").json()
        self.assertTrue(first["has_more"])
        second = self.get(url=self.url, data={"limit": "2", "cursor": first["next_cursor"]}).json()
        self.assertFalse(second["has_more"])
        self.assertEqual(len({i["plan_id"] for i in first["items"] + second["items"]}), 3)
        _, other_raw = issue_token(self.binding, expires_at=timezone.now() + timedelta(days=1), plans_read=True)
        self.assertEqual(self.get(raw=other_raw, data={"cursor": first["next_cursor"]}).status_code, 400)
        self.assertEqual(self.get(data={"cursor": first["next_cursor"] + "x"}).status_code, 400)
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 1000):
            self.assertEqual(self.get(data={"cursor": first["next_cursor"]}).status_code, 400)

    def test_query_bounds_and_method(self):
        for query in ["limit=0", "limit=101", "limit=-1", "limit=abc", "limit=1&limit=2", "cursor=", "cursor=" + "x" * 2049]:
            self.assertEqual(self.get(url=self.url + "?" + query).status_code, 400)
        r = self.client.post(self.url, secure=True, HTTP_AUTHORIZATION="Bearer " + self.raw)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r["Allow"], "GET")

    def test_rotation_overlap_and_rate_limit(self):
        _, new_raw = issue_token(self.binding, expires_at=timezone.now() + timedelta(days=1), plans_read=True)
        self.assertEqual(self.get(raw=new_raw).status_code, 200)
        self.assertEqual(self.get().status_code, 200)
        CAFServiceToken.objects.filter(pk=self.token.pk).update(rate_window=int(timezone.now().timestamp()) // 60, rate_count=60)
        response = self.get()
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.json()["error"]["retryable"])
        self.assertIn("Retry-After", response)
        CAFServiceToken.objects.filter(pk=self.token.pk).update(active=False)
        self.assertEqual(self.get().status_code, 401)
        self.assertEqual(self.get(raw=new_raw).status_code, 200)

    def test_database_outage_is_safe_json(self):
        with patch("core.caf_catalog.CAFServiceToken.objects.select_related", side_effect=DatabaseError("PRIVATE-CONNECTION-DETAIL")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE", response.content.decode())

    def test_setup_command_file_only_rotation_and_no_overwrite(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            output = StringIO()
            kwargs = dict(actor="owner", company_id=self.tenant.company_id, source="caf-portal", caf_company_id="caf-company-a", token_file=str(path))
            call_command("configure_caf_catalog", stdout=output, **kwargs)
            raw = path.read_text().strip()
            self.assertNotIn(raw, output.getvalue())
            self.assertEqual(self.get(raw=raw).status_code, 200)
            count = CAFServiceToken.objects.count()
            with self.assertRaises(CommandError):
                call_command("configure_caf_catalog", stdout=StringIO(), **kwargs)
            self.assertEqual(CAFServiceToken.objects.count(), count)
            self.assertEqual(path.read_text().strip(), raw)

    def test_setup_command_audit_failure_removes_secret_and_rolls_back(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            count = CAFServiceToken.objects.count()
            with patch("core.management.commands.configure_caf_catalog.AuditEvent.objects.create", side_effect=RuntimeError("audit failure")):
                with self.assertRaises(CommandError):
                    call_command("configure_caf_catalog", actor="owner", company_id=self.tenant.company_id,
                                 source="caf-portal", caf_company_id="caf-company-a", token_file=str(path), stdout=StringIO())
            self.assertFalse(path.exists())
            self.assertEqual(CAFServiceToken.objects.count(), count)

    def test_setup_requires_owner_and_rejects_remapping(self):
        with TemporaryDirectory() as directory:
            kwargs = dict(actor="owner", company_id=self.tenant.company_id, source="caf-portal",
                          caf_company_id="caf-company-a", token_file=str(Path(directory) / "token"), stdout=StringIO())
            Membership.objects.filter(user=self.actor).update(role="operator")
            with self.assertRaises(CommandError):
                call_command("configure_caf_catalog", **kwargs)
            Membership.objects.filter(user=self.actor).update(role="owner")
            CAFCompanyBinding.objects.create(source="other-source", caf_company_id="caf-company-a", tenant=self.other)
            kwargs["source"] = "other-source"
            with self.assertRaises(CommandError):
                call_command("configure_caf_catalog", **kwargs)
            self.assertFalse(Path(kwargs["token_file"]).exists())

    def test_direct_writes_cannot_move_bindings_or_tokens(self):
        other_binding = CAFCompanyBinding.objects.create(source="caf-portal", caf_company_id="caf-company-b", tenant=self.other)
        for updates in [{"tenant": self.other}, {"source": "other-source"}, {"caf_company_id": "different-id"}]:
            with self.subTest(updates=updates), self.assertRaises(DatabaseError), transaction.atomic():
                CAFCompanyBinding.objects.filter(pk=self.binding.pk).update(**updates)
        for updates in [{"binding": other_binding}, {"secret_digest": "a" * 64}]:
            with self.subTest(updates=updates), self.assertRaises(DatabaseError), transaction.atomic():
                CAFServiceToken.objects.filter(pk=self.token.pk).update(**updates)
