from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .caf_connections import ConnectionTestError, fingerprint, open_token, test_remote as verify_remote
from .models import (AuditEvent, CAFCompanyBinding, CAFConnection, CAFFranchiseBinding, CAFServiceToken,
                     Membership, Plan, Subscriber, Tenant)
from .test_caf_provisioning import PRODUCTION_FIXTURE


@override_settings(**{**PRODUCTION_FIXTURE, "CAF_CATALOG_ENABLED": True})
class CAFSettingsTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user("settings-owner")
        self.tenant = Tenant.objects.create(slug="settings", name="Settings pilot")
        Membership.objects.create(user=self.actor, tenant=self.tenant, role="owner")
        self.client.force_login(self.actor)
        self.url = f"/companies/{self.tenant.company_id}/integrations/caf/"
        self.key = "caf_read_" + "S" * 48
        self.save_body = {"action": "save", "source": "caf-portal", "caf_company_id": "company-a",
                          "origin": "https://caf.example.test", "caf_read_key": self.key}

    def configured(self):
        self.assertContains(self.client.post(self.url, self.save_body), "Connection saved")
        self.assertContains(self.client.post(self.url, {"action": "map_franchise", "caf_franchise_id": "franchise-a",
                                                      "name": "CAF franchise"}), "Franchise mapped")
        return CAFConnection.objects.get()

    def successful_test(self):
        with patch("core.caf_connections.directory", side_effect=[
            [{"id": "company-a", "is_active": True}],
            [{"id": "franchise-a", "company_id": "company-a", "is_active": True}],
        ]):
            return self.client.post(self.url, {"action": "test"})

    def test_owner_only_and_csrf_required(self):
        for role in ("operator", "viewer"):
            Membership.objects.filter(user=self.actor).update(role=role)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.save_body).status_code, 403)
        Membership.objects.filter(user=self.actor).delete()
        self.actor.is_superuser = True
        self.actor.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        Membership.objects.create(user=self.actor, tenant=self.tenant, role="owner")
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(self.url, self.save_body).status_code, 403)

    def test_secret_encrypted_write_only_blank_preserves_clear_disables(self):
        cfg = self.configured()
        self.assertNotIn(self.key, cfg.token_ciphertext)
        self.assertEqual(open_token(cfg), self.key)
        response = self.client.get(self.url)
        self.assertNotContains(response, self.key)
        self.assertNotContains(response, cfg.token_ciphertext)
        self.assertIn("no-store", response["Cache-Control"])
        prior = cfg.token_ciphertext
        self.client.post(self.url, {**self.save_body, "caf_read_key": ""})
        cfg.refresh_from_db()
        self.assertEqual(prior, cfg.token_ciphertext)
        self.assertFalse(cfg.staged_enabled)
        self.client.post(self.url, {**self.save_body, "caf_read_key": "", "clear_key": "on"})
        cfg.refresh_from_db()
        self.assertEqual(cfg.token_ciphertext, "")
        self.assertFalse(cfg.staged_enabled)
        self.assertFalse(Subscriber.objects.exists())
        self.assertNotIn(self.key, str(list(AuditEvent.objects.values())))

    def test_encryption_key_rotation_and_missing_old_key_fail_closed(self):
        cfg = self.configured()
        with override_settings(CAF_CREDENTIAL_KEY_ID="v2", CAF_CREDENTIAL_KEYS={
            **PRODUCTION_FIXTURE["CAF_CREDENTIAL_KEYS"], "v2": Fernet.generate_key().decode(),
        }):
            self.assertEqual(open_token(cfg), self.key)
            self.client.post(self.url, self.save_body)
            cfg.refresh_from_db()
            self.assertEqual(cfg.encryption_key_id, "v2")
            self.assertEqual(open_token(cfg), self.key)
        self.assertContains(self.client.post(self.url, {"action": "test"}), "caf_configuration_failed")
        cfg.refresh_from_db()
        self.assertFalse(cfg.staged_enabled)

    def test_https_allowlist_no_redirects_or_origin_change_secret_forwarding(self):
        for origin in ("http://caf.example.test", "https://caf.example.test/", "https://evil.example.test",
                       "https://caf.example.test@evil.example.test", "https://caf.example.test?x=1"):
            self.client.post(self.url, {**self.save_body, "origin": origin})
            self.assertFalse(CAFConnection.objects.exists())
        cfg = self.configured()
        with override_settings(CAF_API_ALLOWED_ORIGINS=["https://caf.example.test", "https://other.example.test"]):
            response = self.client.post(self.url, {**self.save_body, "origin": "https://other.example.test", "caf_read_key": ""})
            self.assertContains(response, "Changing origin requires")
        cfg.refresh_from_db()
        self.assertEqual(cfg.origin, "https://caf.example.test")

    def test_immutable_company_and_source_not_remapped(self):
        self.configured()
        for field in ("source", "caf_company_id"):
            self.assertContains(self.client.post(self.url, {**self.save_body, field: "other"}), "identity is immutable")
        binding = CAFCompanyBinding.objects.get()
        self.assertEqual(binding.source, "caf-portal")
        self.assertEqual(binding.caf_company_id, "company-a")

    def test_one_time_four_grant_key_status_expiry_and_revocation(self):
        self.configured()
        response = self.client.post(self.url, {"action": "issue", "expires_days": "1", "plans_read": "on",
            "reservations_write": "on", "provisionings_write": "on", "receipts_read": "on"})
        key = response.context["issued_key"]
        self.assertTrue(key.startswith("nlcaf_"))
        self.assertContains(response, key)
        self.assertNotContains(self.client.get(self.url), key)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(key, str(list(CAFServiceToken.objects.values())))
        self.assertNotIn(key, str(list(AuditEvent.objects.values())))
        url = "/api/integrations/ecaf/v1/connection-status"
        status = self.client.get(url, secure=True, HTTP_AUTHORIZATION="Bearer " + key)
        self.assertEqual(status.status_code, 200)
        data = status.json()
        self.assertEqual(data["company_ref"], {"id": "company-a"})
        self.assertEqual(data["franchise_refs"], [{"id": "franchise-a"}])
        self.assertTrue(all(data["grants"].values()))
        self.assertFalse(data["staged_enabled"])
        token = CAFServiceToken.objects.get()
        CAFServiceToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(url, secure=True, HTTP_AUTHORIZATION="Bearer " + key).status_code, 401)
        CAFServiceToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() + timedelta(days=1))
        self.client.post(self.url, {"action": "revoke", "token_id": str(token.pk)})
        self.assertEqual(self.client.get(url, secure=True, HTTP_AUTHORIZATION="Bearer " + key).status_code, 401)

    def test_wrong_tenant_key_and_plan_actions_do_not_mutate_foreign_records(self):
        self.configured()
        other = Tenant.objects.create(slug="foreign", name="Foreign")
        foreign = CAFCompanyBinding.objects.create(tenant=other, source="caf-portal", caf_company_id="foreign")
        from .caf_catalog import issue_token
        token, _ = issue_token(foreign, expires_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.client.post(self.url, {"action": "revoke", "token_id": str(token.pk)}).status_code, 404)
        token.refresh_from_db()
        self.assertTrue(token.active)
        plan = Plan.objects.create(tenant=other, name="Foreign", upload_kbps=10, download_kbps=10)
        self.assertEqual(self.client.post(self.url, {"action": "publish", "plan_id": str(plan.pk), "duration_seconds": "10"}).status_code, 404)

    def test_test_and_enable_are_separate_and_config_changes_disable(self):
        cfg = self.configured()
        self.assertContains(self.client.post(self.url, {"action": "enable"}), "Test the current")
        self.assertContains(self.successful_test(), "scopes verified")
        cfg.refresh_from_db()
        self.assertFalse(cfg.staged_enabled)
        with override_settings(CAF_PRODUCTION_STAGED_ENABLED=False):
            self.assertContains(self.client.post(self.url, {"action": "enable"}), "gates must be enabled")
        self.assertContains(self.client.post(self.url, {"action": "enable"}), "Staged provisioning enabled")
        cfg.refresh_from_db()
        self.assertTrue(cfg.staged_enabled)
        self.client.post(self.url, {**self.save_body, "caf_read_key": ""})
        cfg.refresh_from_db()
        self.assertFalse(cfg.staged_enabled)
        self.assertEqual(cfg.tested_fingerprint, "")

    def test_franchise_reactivation_preserves_number_and_requires_retest(self):
        cfg = self.configured()
        self.successful_test()
        self.client.post(self.url, {"action": "enable"})
        mapping = CAFFranchiseBinding.objects.get()
        number = mapping.franchise_id
        self.client.post(self.url, {"action": "disable_franchise", "franchise_id": str(mapping.pk)})
        self.client.post(self.url, {"action": "enable_franchise", "franchise_id": str(mapping.pk)})
        mapping.refresh_from_db()
        cfg.refresh_from_db()
        self.assertTrue(mapping.active)
        self.assertEqual(mapping.franchise_id, number)
        self.assertFalse(cfg.staged_enabled)
        self.assertEqual(cfg.tested_fingerprint, "")

    def test_foreign_directory_and_missing_franchise_fail_scope_verification(self):
        cfg = self.configured()
        for pages in ([[]], [[{"id": "foreign", "is_active": True}]],
                      [[{"id": "company-a", "is_active": True}], []],
                      [[{"id": "company-a", "is_active": True}], [{"id": "franchise-a", "company_id": "foreign", "is_active": True}]]):
            with patch("core.caf_connections.directory", side_effect=pages):
                with self.assertRaises(ConnectionTestError):
                    verify_remote(cfg)
        self.assertFalse(CAFConnection.objects.get().staged_enabled)

    def test_paginated_directory_checks_all_pages_and_detects_cursor_loop(self):
        cfg = self.configured()
        with patch("core.caf_connections.fetch_page", side_effect=[
            {"items": [{"id": "company-a", "is_active": True}], "has_more": False, "next_cursor": None},
            {"items": [{"id": "franchise-b", "company_id": "company-a", "is_active": True}], "has_more": True, "next_cursor": "next"},
            {"items": [{"id": "franchise-a", "company_id": "company-a", "is_active": True}], "has_more": False, "next_cursor": None},
        ]):
            self.assertEqual(verify_remote(cfg), fingerprint(cfg))
        from .caf_connections import directory
        with patch("core.caf_connections.fetch_page", return_value={"items": [{}], "has_more": True, "next_cursor": "loop"}):
            with self.assertRaisesRegex(ConnectionTestError, "caf_invalid_pagination"):
                directory(cfg, "/api/integrations/radius/v1/companies")

    def test_redirect_and_non_json_do_not_disclose_response_or_follow(self):
        from .caf_connections import fetch_page
        cfg = self.configured()
        with patch("core.caf_connections.http.client.HTTPSConnection") as http:
            response = http.return_value.getresponse.return_value
            response.status = 302
            with self.assertRaisesRegex(ConnectionTestError, "caf_http_failed"):
                fetch_page(cfg, "/api/integrations/radius/v1/companies")
            http.return_value.request.assert_called_once()
            response.status = 200
            response.getheader.return_value = "text/html"
            with self.assertRaisesRegex(ConnectionTestError, "caf_invalid_response"):
                fetch_page(cfg, "/api/integrations/radius/v1/companies")

    def test_publish_and_republish_version_in_owner_ui(self):
        plan = Plan.objects.create(tenant=self.tenant, name="Pilot", upload_kbps=10, download_kbps=10)
        body = {"action": "publish", "plan_id": str(plan.pk), "duration_seconds": "604800"}
        self.assertContains(self.client.post(self.url, body), "Plan publication updated")
        plan.name += " "
        plan.save()
        self.client.post(self.url, body)
        plan.refresh_from_db()
        self.assertEqual(plan.cafplanpublication.version, 2)

    def test_read_only_key_has_no_write_grant(self):
        self.configured()
        response = self.client.post(self.url, {"action": "issue", "expires_days": "1", "plans_read": "on"})
        key = response.context["issued_key"]
        response = self.client.post("/api/integrations/ecaf/v1/username-reservations", data="{}", content_type="application/json",
                                    secure=True, HTTP_AUTHORIZATION="Bearer " + key)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "scope_denied")

    def test_read_only_preflight_rejects_unverified_company_and_stale_publication(self):
        self.configured()
        with self.assertRaises(CommandError):
            call_command("check_caf_staged", company_id=self.tenant.company_id, require_enabled=True, stdout=StringIO())
        self.successful_test()
        self.client.post(self.url, {"action": "enable"})
        plan = Plan.objects.create(tenant=self.tenant, name="Pilot", upload_kbps=10, download_kbps=10)
        self.client.post(self.url, {"action": "publish", "plan_id": str(plan.pk), "duration_seconds": "3600"})
        output = StringIO()
        call_command("check_caf_staged", company_id=self.tenant.company_id, require_enabled=True, stdout=output)
        self.assertIn("eligible publications 1", output.getvalue())
        plan.name += " "
        plan.save()
        with self.assertRaises(CommandError):
            call_command("check_caf_staged", company_id=self.tenant.company_id, require_enabled=True, stdout=StringIO())
        self.assertFalse(Subscriber.objects.exists())

    def test_trusted_proxy_produces_https_return_without_trusting_other_peers(self):
        self.configured()
        url = f"/companies/{self.tenant.company_id}/onboard/"
        with override_settings(CAF_FORM_URL="https://caf.example.test/caf/new",
                               CAF_FORM_ALLOWED_ORIGINS=["https://caf.example.test"], CAF_CATALOG_PROXY_IPS=["10.2.0.1"]):
            response = self.client.get(url, REMOTE_ADDR="10.2.0.1", HTTP_X_FORWARDED_PROTO="https")
            self.assertIn("returnTo=https%3A%2F%2F", response["Location"])
            untrusted = self.client.get(url, REMOTE_ADDR="10.2.0.2", HTTP_X_FORWARDED_PROTO="https")
            self.assertIn("returnTo=http%3A%2F%2F", untrusted["Location"])
        with override_settings(CAF_FORM_URL="https://other.example.test/caf/new",
                               CAF_FORM_ALLOWED_ORIGINS=["https://other.example.test"]):
            self.assertEqual(self.client.get(url, secure=True).status_code, 503)
