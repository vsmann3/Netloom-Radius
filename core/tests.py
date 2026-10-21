import uuid
import base64
import hashlib
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AuditEvent, Membership, NAS, Plan, RouterAction, Session, Subscriber, Tenant
from .services import require_membership, suspend_subscriber


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.a = Tenant.objects.create(slug="a", name="ISP A")
        self.b = Tenant.objects.create(slug="b", name="ISP B")
        self.owner = get_user_model().objects.create_user("owner", password="management-password")
        self.viewer = get_user_model().objects.create_user("viewer")
        Membership.objects.create(user=self.owner, tenant=self.a, role="owner")
        Membership.objects.create(user=self.viewer, tenant=self.a, role="viewer")
        self.pa = Plan.objects.create(tenant=self.a, name="A", upload_kbps=10000, download_kbps=20000)
        self.pb = Plan.objects.create(tenant=self.b, name="B", upload_kbps=30000, download_kbps=50000)
        self.sa = Subscriber.objects.create(tenant=self.a, username="same-user", password_hash=make_password("password-A"), plan=self.pa, expires_at=self.now + timedelta(days=1))
        self.sb = Subscriber.objects.create(tenant=self.b, username="same-user", password_hash=make_password("password-B"), plan=self.pb, expires_at=self.now + timedelta(days=1))
        self.na = NAS.objects.create(tenant=self.a, name="NAS A", source_ip="192.0.2.1", secret_ref="nas-a")
        self.nb = NAS.objects.create(tenant=self.b, name="NAS B", source_ip="192.0.2.2", secret_ref="nas-b")
        self.session = Session.objects.create(tenant=self.a, nas=self.na, subscriber=self.sa, session_id="session-1", nas_epoch=uuid.uuid4(), started_at=self.now, last_seen_at=self.now)

    def assert_integrity(self, fn):
        with self.assertRaises(IntegrityError), transaction.atomic():
            fn()

    def test_database_blocks_cross_tenant_plan_insert_and_update(self):
        self.assert_integrity(lambda: Subscriber.objects.create(tenant=self.a, username="invalid", password_hash="!", plan=self.pb, expires_at=self.now))
        self.assert_integrity(lambda: Subscriber.objects.filter(pk=self.sa.pk).update(plan=self.pb))
        self.assert_integrity(lambda: Plan.objects.filter(pk=self.pa.pk).update(tenant=self.b))

    def test_database_blocks_cross_tenant_session_and_action(self):
        self.assert_integrity(lambda: Session.objects.filter(pk=self.session.pk).update(nas=self.nb))
        self.assert_integrity(lambda: Session.objects.filter(pk=self.session.pk).update(subscriber=self.sb))
        self.assert_integrity(lambda: RouterAction.objects.create(tenant=self.b, session=self.session))

    def test_database_rejects_duplicate_username_within_tenant(self):
        self.assert_integrity(lambda: Subscriber.objects.create(tenant=self.a, username="same-user", password_hash="!", plan=self.pa, expires_at=self.now))

    def test_database_preserves_nas_source_and_session_identity(self):
        self.assert_integrity(lambda: NAS.objects.create(tenant=self.b, name="conflict", source_ip=self.na.source_ip, secret_ref="conflict"))
        self.assert_integrity(lambda: Session.objects.create(tenant=self.a, nas=self.na, subscriber=self.sa, session_id=self.session.session_id, nas_epoch=self.session.nas_epoch, started_at=self.now, last_seen_at=self.now))
        Session.objects.create(tenant=self.a, nas=self.na, subscriber=self.sa, session_id=self.session.session_id, nas_epoch=uuid.uuid4(), started_at=self.now, last_seen_at=self.now)

    def test_suspension_is_atomic_audited_and_idempotent(self):
        subscriber, queued = suspend_subscriber(actor=self.owner, tenant_id=self.a.id, subscriber_id=self.sa.id)
        self.assertEqual((subscriber.status, queued), ("suspended", 1))
        self.assertEqual(RouterAction.objects.get().session_id, self.session.id)
        self.assertEqual(AuditEvent.objects.get().actor_id, self.owner.id)
        _, queued = suspend_subscriber(actor=self.owner, tenant_id=self.a.id, subscriber_id=self.sa.id)
        self.assertEqual(queued, 0)
        self.assertEqual(RouterAction.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_audit_failure_rolls_back_business_state_and_outbox(self):
        with patch("core.services.AuditEvent.objects.create", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                suspend_subscriber(actor=self.owner, tenant_id=self.a.id, subscriber_id=self.sa.id)
        self.sa.refresh_from_db()
        self.assertEqual(self.sa.status, "active")
        self.assertFalse(RouterAction.objects.exists())

    def test_suspension_ignores_closed_sessions(self):
        Session.objects.filter(pk=self.session.pk).update(stopped_at=self.now)
        _, count = suspend_subscriber(actor=self.owner, tenant_id=self.a.id, subscriber_id=self.sa.id)
        self.assertEqual(count, 0)

    def test_viewer_and_platform_user_cannot_write(self):
        with self.assertRaises(PermissionDenied):
            suspend_subscriber(actor=self.viewer, tenant_id=self.a.id, subscriber_id=self.sa.id)
        platform = get_user_model().objects.create_superuser("platform", password="platform-password")
        with self.assertRaises(PermissionDenied):
            require_membership(platform, self.a.id)

    def test_cross_tenant_target_rejected_even_for_authorized_owner(self):
        with self.assertRaises(Http404):
            suspend_subscriber(actor=self.owner, tenant_id=self.a.id, subscriber_id=self.sb.id)
        with self.assertRaises(PermissionDenied):
            suspend_subscriber(actor=self.owner, tenant_id=self.b.id, subscriber_id=self.sb.id)
        self.assertFalse(RouterAction.objects.exists())

    def test_api_excludes_passwords_and_other_tenants(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("subscribers", args=[self.a.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x["id"] for x in response.json()["subscribers"]], [str(self.sa.id)])
        self.assertNotIn("password", response.content.decode())
        self.assertEqual(self.client.get(reverse("subscribers", args=[self.b.id])).status_code, 403)

    def test_api_requires_login_post_and_csrf(self):
        url = reverse("suspend", args=[self.a.id, self.sa.id])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_seed_requires_opt_in_and_preserves_existing_state(self):
        with self.assertRaises(CommandError):
            call_command("seed_lab", synthetic_subscribers=1)
        call_command("seed_lab", tenant="a", synthetic_subscribers=2, allow_synthetic_data=True, verbosity=0)
        generated = Subscriber.objects.get(tenant=self.a, username="synthetic-0001")
        self.assertTrue(generated.password_hash.startswith("!"))
        Subscriber.objects.filter(pk=generated.pk).update(status="suspended")
        call_command("seed_lab", tenant="a", synthetic_subscribers=2, allow_synthetic_data=True, verbosity=0)
        generated.refresh_from_db()
        self.assertEqual(generated.status, "suspended")
        self.assertEqual(Subscriber.objects.filter(tenant=self.a, username__startswith="synthetic-").count(), 2)

    def test_password_command_uses_pap_hash_and_audits(self):
        with patch("getpass.getpass", return_value="A-long-random-PAP-password!42"):
            call_command("set_subscriber_password", tenant="a", username="same-user", actor="owner", verbosity=0)
        self.sa.refresh_from_db()
        self.assertTrue(self.sa.password_hash.startswith("pbkdf2_sha256$"))
        self.assertTrue(check_password("A-long-random-PAP-password!42", self.sa.password_hash))
        self.assertEqual(AuditEvent.objects.get().action, "subscriber.password_set")
        self.assertNotEqual(self.sb.password_hash, self.sa.password_hash)

    def test_password_command_denies_viewer_before_prompt(self):
        with patch("getpass.getpass") as prompt:
            with self.assertRaises(PermissionDenied):
                call_command("set_subscriber_password", tenant="a", username="same-user", actor="viewer")
        prompt.assert_not_called()

    def test_client_renderer_uses_registered_addresses_and_preserves_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret_dir = root / "nas"
            secret_dir.mkdir()
            (secret_dir / "nas-a").write_text("a" * 64)
            (secret_dir / "nas-b").write_text("b" * 64)
            output = root / "clients.conf"
            call_command("render_radius_clients", secret_dir=str(secret_dir), output=str(output), verbosity=0)
            rendered = output.read_text()
            self.assertIn("ipaddr = 192.0.2.1", rendered)
            self.assertIn("ipaddr = 192.0.2.2", rendered)
            self.assertIn("require_message_authenticator = yes", rendered)
            (secret_dir / "nas-b").write_text("a" * 64)
            with self.assertRaises(CommandError):
                call_command("render_radius_clients", secret_dir=str(secret_dir), output=str(output))
            self.assertEqual(output.read_text(), rendered)
            (secret_dir / "nas-b").write_text("b" * 64)
            NAS.objects.filter(pk=self.na.pk).update(secret_ref="../escape")
            with self.assertRaises(CommandError):
                call_command("render_radius_clients", secret_dir=str(secret_dir), output=str(output))
            self.assertEqual(output.read_text(), rendered)

    def test_integration_seed_refuses_normal_database(self):
        with self.assertRaises(CommandError):
            call_command("seed_radius_integration")


@skipUnless(connection.vendor == "mysql", "Requires MariaDB authorization view")
class RadiusSQLTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.tenant = Tenant.objects.create(slug="sql-a", name="SQL A")
        self.plan = Plan.objects.create(tenant=self.tenant, name="SQL", upload_kbps=10000, download_kbps=20000)
        self.nas = NAS.objects.create(tenant=self.tenant, name="SQL NAS", source_ip="192.0.2.1", secret_ref="sql")
        self.subscriber = Subscriber.objects.create(
            tenant=self.tenant, plan=self.plan, username="same-user",
            password_hash=make_password("Unicode-credential-\u00e9!", hasher="pbkdf2_sha256"),
            expires_at=self.now + timedelta(hours=1),
        )

    def rows(self, source="192.0.2.1", username="same-user"):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pap_password, rate_limit, session_timeout FROM radius_authorization WHERE source_ip=%s AND username=BINARY %s", [source, username])
            return cursor.fetchall()

    def module_query(self, name):
        module = (settings.BASE_DIR / "deploy/radius/mods-enabled/netloom_sql").read_text()
        query = module.split(name + ' = "', 1)[1].split('"', 1)[0].replace("\\\n", "")
        return query.replace("'%{Packet-Src-IP-Address}'", "%s").replace("'%{SQL-User-Name}'", "%s")

    def test_pap_format_preserves_digest_salt_and_rounds(self):
        credential, rate, timeout = self.rows()[0]
        self.assertTrue(credential.startswith("$PBKDF2$HMACSHA2+256:"))
        parameters, digest = credential.removeprefix("$PBKDF2$").split("$")
        algorithm, rounds, salt = parameters.split(":")
        expected = hashlib.pbkdf2_hmac("sha256", "Unicode-credential-\u00e9!".encode(), base64.b64decode(salt), int(rounds))
        self.assertEqual(base64.b64decode(digest), expected)
        self.assertEqual(rate, "10000k/20000k")
        self.assertTrue(1 <= timeout <= 3600)
        with connection.cursor() as cursor:
            cursor.execute(self.module_query("authorize_check_query"), ["192.0.2.1", "same-user"])
            row = cursor.fetchone()
            self.assertEqual(row[2], "Password-With-Header")
            self.assertEqual(row[3], "{X-PBKDF2}" + credential)

    def test_deployed_reply_query_handles_driver_connection_collation(self):
        query = self.module_query("authorize_reply_query")
        with connection.cursor() as cursor:
            try:
                for charset in ("latin1", "utf8mb4"):
                    cursor.execute(f"SET NAMES {charset}")
                    cursor.execute(query, ["192.0.2.1", "same-user"] * 3)
                    reply = {row[2]: row[3] for row in cursor.fetchall()}
                    self.assertEqual(reply["Mikrotik-Rate-Limit"], "10000k/20000k")
                    self.assertEqual(reply["Acct-Interim-Interval"], "300")
                    self.assertTrue(1 <= int(reply["Session-Timeout"]) <= 3600)
            finally:
                cursor.execute("SET NAMES utf8mb4")

    def test_same_name_other_tenant_has_separate_password_and_plan(self):
        tenant = Tenant.objects.create(slug="sql-b", name="SQL B")
        plan = Plan.objects.create(tenant=tenant, name="SQL B", upload_kbps=30000, download_kbps=50000)
        NAS.objects.create(tenant=tenant, name="B", source_ip="192.0.2.2", secret_ref="b")
        Subscriber.objects.create(tenant=tenant, plan=plan, username="same-user", password_hash=make_password("Other-credential!", hasher="pbkdf2_sha256"), expires_at=self.now + timedelta(hours=1))
        self.assertEqual(self.rows()[0][1], "10000k/20000k")
        self.assertEqual(self.rows(source="192.0.2.2")[0][1], "30000k/50000k")
        self.assertNotEqual(self.rows()[0][0], self.rows(source="192.0.2.2")[0][0])
        self.assertFalse(self.rows(source="192.0.2.99"))
        self.assertFalse(self.rows(username="Same-User"))

    def test_state_changes_immediately_remove_authorization(self):
        Subscriber.objects.filter(pk=self.subscriber.pk).update(status="suspended")
        self.assertFalse(self.rows())
        Subscriber.objects.filter(pk=self.subscriber.pk).update(status="active", expires_at=self.now - timedelta(seconds=1))
        self.assertFalse(self.rows())
        Subscriber.objects.filter(pk=self.subscriber.pk).update(expires_at=self.now + timedelta(hours=1))
        NAS.objects.filter(pk=self.nas.pk).update(enabled=False)
        self.assertFalse(self.rows())
        NAS.objects.filter(pk=self.nas.pk).update(enabled=True)
        Tenant.objects.filter(pk=self.tenant.pk).update(active=False)
        self.assertFalse(self.rows())

    def test_unsupported_and_malformed_hashes_are_not_exposed(self):
        for credential in ("!unusable", "md5$salt$00000000000000000000000000000000", "pbkdf2_sha256$0$salt$invalid", self.subscriber.password_hash.replace("pbkdf2_sha256$", "pbkdf2_sha1$")):
            Subscriber.objects.filter(pk=self.subscriber.pk).update(password_hash=credential)
            self.assertFalse(self.rows())
