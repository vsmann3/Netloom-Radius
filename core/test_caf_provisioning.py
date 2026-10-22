import copy
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .caf_catalog import issue_token, publish_plan
from .models import (CAFCompanyBinding, CAFConnection, CAFDeliveryReceipt, CAFCustomerLink, CAFFranchiseBinding,
                     CAFReservation, CAFServiceRequest, CAFServiceToken, Membership, Plan, Subscriber, Tenant)


PRODUCTION_FIXTURE = dict(CAF_PRODUCTION_STAGED_ENABLED=True, CAF_PROVISIONING_ENABLED=True,
    CAF_FINGERPRINT_KEYS={"v1": "ab" * 32}, CAF_FINGERPRINT_KEY_ID="v1",
    CAF_CREDENTIAL_KEYS={"v1": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg="},
    CAF_API_ALLOWED_ORIGINS=["https://caf.example.test"])


@override_settings(**PRODUCTION_FIXTURE)
class CAFProvisioningTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="caf-demo", name="CAF Demo")
        self.binding = CAFCompanyBinding.objects.create(tenant=self.tenant, source="caf-portal", caf_company_id="company-a")
        self.franchise = CAFFranchiseBinding.objects.create(company=self.binding, caf_franchise_id="franchise-a", name="Test franchise")
        # Existing protocol suite runs behind an explicit verified company gate.
        from .caf_connections import fingerprint, seal_token
        key_id, ciphertext = seal_token(self.binding, "https://caf.example.test", "fixture." + "x" * 40)
        config = CAFConnection.objects.create(binding=self.binding, origin="https://caf.example.test",
            token_ciphertext=ciphertext, encryption_key_id=key_id, staged_enabled=True, test_result="ok")
        config.tested_fingerprint = fingerprint(config)
        config.save()
        self.actor = get_user_model().objects.create_user("owner")
        Membership.objects.create(user=self.actor, tenant=self.tenant, role="owner")
        self.plan = Plan.objects.create(tenant=self.tenant, name="300 Mbps", download_kbps=300000, upload_kbps=300000)
        publish_plan(actor=self.actor, plan_id=self.plan.pk, duration_seconds=2592000)
        self.token, self.secret = issue_token(self.binding, expires_at=timezone.now() + timedelta(days=1))
        CAFServiceToken.objects.filter(pk=self.token.pk).update(reservations_write=True, provisionings_write=True, receipts_read=True)
        self.reservation_body = {"customer_id": "1000000123", "service_request_id": str(uuid.uuid4()), "username": "test.customer",
            "plan_id": str(self.plan.pk), "plan_version": 1, "company_ref": {"id": "company-a"}, "franchise_ref": {"id": "franchise-a"}}

    def post(self, path, body, key=None, raw=None):
        return self.client.post(path, data=json.dumps(body) if raw is None else raw, content_type="application/json", secure=True,
            HTTP_AUTHORIZATION="Bearer " + self.secret, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def reserve(self, body=None, key=None):
        return self.post("/api/integrations/ecaf/v1/username-reservations", body or self.reservation_body, key)

    def bundle(self, reservation=None):
        reservation = reservation or self.reserve().json()
        event = json.loads((__import__('pathlib').Path(__file__).parent / "caf_schemas/ecaf-event.example.json").read_text())
        event.update(customer_id=self.reservation_body["customer_id"], company_ref={"id": "company-a"}, franchise_ref={"id": "franchise-a"})
        return {"schema_version": "2.0", "provisioning_request_id": str(uuid.uuid4()), "supersedes_request_id": None, "approval": event,
                "service": {"service_request_id": self.reservation_body["service_request_id"], "reservation_id": reservation["reservation_id"],
                            "username": self.reservation_body["username"], "plan_id": str(self.plan.pk), "initial_password": "Demo-Radius#Password-825"}}

    def provision(self, body):
        return self.post("/api/integrations/ecaf/v2/provisionings", body, body["provisioning_request_id"])

    def test_reservation_is_scoped_and_idempotent(self):
        key = uuid.uuid4()
        response = self.reserve(key=key)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.reserve(key=key).json(), response.json())
        changed = {**self.reservation_body, "username": "different"}
        self.assertEqual(self.reserve(changed, key).status_code, 409)
        self.assertEqual(CAFReservation.objects.count(), 1)

    def test_tenant_username_namespace_checks_case(self):
        self.reserve()
        changed = {**self.reservation_body, "service_request_id": str(uuid.uuid4()), "username": "TEST.customer"}
        self.assertEqual(self.reserve(changed).json()["error"]["code"], "username_unavailable")
        self.assertEqual(CAFServiceRequest.objects.count(), 1)

    def test_scope_and_unpublished_plan_fail_closed(self):
        for body in [{**self.reservation_body, "company_ref": {"id": "other"}},
                     {**self.reservation_body, "franchise_ref": {"id": "other"}}]:
            self.assertEqual(self.reserve(body).status_code, 422)
        self.plan.name = "Changed"
        self.plan.save()
        self.assertEqual(self.reserve().json()["error"]["code"], "plan_changed")
        self.assertFalse(CAFServiceRequest.objects.exists())

    def test_approved_provisioning_creates_suspended_service_and_durable_receipt(self):
        body = self.bundle()
        response = self.provision(body)
        self.assertEqual(response.status_code, 202, response.content)
        self.assertTrue(response.json()["credential_accepted"])
        self.assertEqual(response.json()["service_status"], "pending_service_setup")
        s = Subscriber.objects.get()
        self.assertEqual(s.status, "suspended")
        self.assertTrue(check_password(body["service"]["initial_password"], s.password_hash))
        self.assertEqual(CAFCustomerLink.objects.get().customer_id, "1000000123")
        read = self.client.get("/api/integrations/ecaf/v2/provisionings/" + body["provisioning_request_id"], secure=True,
                               HTTP_AUTHORIZATION="Bearer " + self.secret)
        self.assertEqual(read.json(), response.json())
        self.assertNotIn(body["service"]["initial_password"], str(list(CAFDeliveryReceipt.objects.values())))

    def test_production_disable_blocks_new_writes_but_preserves_receipt_reconciliation(self):
        body = self.bundle()
        accepted = self.provision(body).json()
        original = Subscriber.objects.get()
        CAFConnection.objects.filter(binding=self.binding).update(staged_enabled=False)
        self.assertEqual(self.provision(body).json()["error"]["code"], "staged_delivery_disabled")
        receipt = self.client.get("/api/integrations/ecaf/v2/provisionings/" + body["provisioning_request_id"], secure=True,
            HTTP_AUTHORIZATION="Bearer " + self.secret)
        self.assertEqual(receipt.json(), accepted)
        unchanged = Subscriber.objects.get()
        self.assertEqual((original.password_hash, original.expires_at), (unchanged.password_hash, unchanged.expires_at))
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_normal_mode_requires_both_server_and_verified_company_gates(self):
        with override_settings(CAF_PRODUCTION_STAGED_ENABLED=False):
            self.assertEqual(self.reserve().json()["error"]["code"], "staged_delivery_disabled")
        CAFConnection.objects.filter(binding=self.binding).update(tested_fingerprint="changed")
        self.assertEqual(self.reserve().status_code, 503)
        self.assertFalse(CAFServiceRequest.objects.exists())

    def test_matching_retry_does_not_reset_radius_owned_password(self):
        body = self.bundle()
        first = self.provision(body)
        s = Subscriber.objects.get()
        s.password_hash = make_password("Later-Radius-Owned-Password")
        s.save()
        self.assertEqual(self.provision(body).json(), first.json())
        s.refresh_from_db()
        self.assertTrue(check_password("Later-Radius-Owned-Password", s.password_hash))
        changed = copy.deepcopy(body)
        changed["service"]["initial_password"] = "Different-Password#825"
        self.assertEqual(self.provision(changed).status_code, 409)
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_unapproved_or_sensitive_extra_fields_never_create_service(self):
        body = self.bundle()
        for status in ["DRAFT", "REJECTED", "SUBMITTED"]:
            bad = copy.deepcopy(body)
            bad["approval"]["caf"]["status"] = status
            self.assertEqual(self.provision(bad).status_code, 400)
        bad = copy.deepcopy(body)
        bad["approval"]["profile"]["idNumber"] = "DO-NOT-SEND"
        self.assertEqual(self.provision(bad).status_code, 400)
        self.assertFalse(Subscriber.objects.exists())

    def test_duplicate_keys_nonfinite_and_missing_key_rejected(self):
        path = "/api/integrations/ecaf/v1/username-reservations"
        for raw in ['{"customer_id":"1000000123","customer_id":"1000000124"}', '{"x":NaN}', '[]']:
            self.assertEqual(self.post(path, {}, raw=raw).status_code, 400)
        response = self.client.post(path, data=json.dumps(self.reservation_body), content_type="application/json", secure=True,
                                    HTTP_AUTHORIZATION="Bearer " + self.secret)
        self.assertEqual(response.status_code, 400)

    def test_canonical_key_order_retry_and_utf8_password_limit(self):
        body = self.bundle()
        too_long = copy.deepcopy(body)
        too_long["service"]["initial_password"] = "Strong#123" + "\U0001f642" * 31
        self.assertEqual(self.provision(too_long).json()["error"]["code"], "invalid_password")
        first = self.provision(body)
        reordered = dict(reversed(list(body.items())))
        reordered["service"] = dict(reversed(list(body["service"].items())))
        retried = self.post("/api/integrations/ecaf/v2/provisionings", {}, key=body["provisioning_request_id"], raw=json.dumps(reordered, indent=2))
        self.assertEqual(retried.json(), first.json())
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_expired_reservation_receipt_allows_only_immutable_leaf_replacement(self):
        body = self.bundle()
        CAFReservation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        failed = self.provision(body)
        self.assertEqual(failed.status_code, 409)
        self.assertFalse(failed.json()["credential_accepted"])
        self.assertFalse(Subscriber.objects.exists())
        reservation = self.reserve().json()
        replacement = copy.deepcopy(body)
        replacement.update(provisioning_request_id=str(uuid.uuid4()), supersedes_request_id=body["provisioning_request_id"])
        replacement["service"]["reservation_id"] = reservation["reservation_id"]
        changed = copy.deepcopy(replacement)
        changed["service"]["initial_password"] = "Changed-Password#827"
        self.assertEqual(self.provision(changed).json()["error"]["code"], "replacement_binding_conflict")
        self.assertEqual(self.provision(replacement).status_code, 202)
        fork = copy.deepcopy(replacement)
        fork["provisioning_request_id"] = str(uuid.uuid4())
        self.assertEqual(self.provision(fork).status_code, 409)
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_missing_fingerprint_key_rolls_back_and_retired_key_blocks_replay(self):
        with override_settings(CAF_FINGERPRINT_KEYS={}):
            self.assertEqual(self.reserve().status_code, 503)
        self.assertFalse(CAFServiceRequest.objects.exists())
        key = uuid.uuid4()
        self.reserve(key=key)
        with override_settings(CAF_FINGERPRINT_KEYS={"v2": "cd" * 32}, CAF_FINGERPRINT_KEY_ID="v2"):
            self.assertEqual(self.reserve(key=key).status_code, 503)

    def test_out_of_order_independent_services_preserve_newest_identity(self):
        newer = self.bundle()
        newer["approval"]["customer_version"] = 3
        newer["approval"]["profile"]["name"] = "Newest approved name"
        self.assertEqual(self.provision(newer).status_code, 202)
        self.reservation_body.update(service_request_id=str(uuid.uuid4()), username="second.connection")
        older = self.bundle()
        older["approval"]["event_id"] = str(uuid.uuid4())
        self.assertEqual(self.provision(older).status_code, 202)
        self.assertEqual(Subscriber.objects.count(), 2)
        link = CAFCustomerLink.objects.get()
        self.assertEqual(link.profile_version, 3)
        self.assertEqual(link.profile["name"], "Newest approved name")

    def test_equal_version_changed_profile_is_conflict(self):
        self.assertEqual(self.provision(self.bundle()).status_code, 202)
        self.reservation_body.update(service_request_id=str(uuid.uuid4()), username="second.connection")
        body = self.bundle()
        body["approval"]["profile"]["name"] = "Conflicting name"
        self.assertEqual(self.provision(body).json()["error"]["code"], "profile_version_conflict")

    @override_settings(CAF_DEMO_LOCAL_HTTP=True, CAF_DEMO_AUTO_ACTIVATE=True)
    def test_isolated_demo_activation_replay_keeps_expiry_anchor(self):
        body = self.bundle()
        first = self.provision(body)
        if connection.vendor != "sqlite":
            self.assertEqual(first.status_code, 503)
            self.assertEqual(first.json()["error"]["code"], "demo_activation_not_isolated")
            self.assertFalse(Subscriber.objects.exists())
            return
        self.assertEqual(first.json()["service_status"], "active")
        expiry = Subscriber.objects.get().expires_at
        self.assertEqual(self.provision(body).json(), first.json())
        self.assertEqual(Subscriber.objects.get().expires_at, expiry)

    def test_transaction_failure_rolls_back_hash_link_and_receipt(self):
        body = self.bundle()
        with patch("core.caf_provisioning._save", side_effect=RuntimeError("storage injection")):
            with self.assertRaises(RuntimeError):
                self.provision(body)
        self.assertFalse(Subscriber.objects.exists())
        self.assertFalse(CAFCustomerLink.objects.exists())
        self.assertFalse(CAFServiceRequest.objects.get().credential_accepted)

    def test_renewal_is_route_bound_idempotent_and_does_not_change_binding(self):
        reservation = self.reserve().json()
        path = "/api/integrations/ecaf/v1/username-reservations/" + reservation["reservation_id"] + "/renew"
        key = uuid.uuid4()
        first = self.post(path, {}, key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), self.post(path, {}, key).json())
        self.assertEqual(first.json()["username"], reservation["username"])
        self.assertEqual(first.json()["plan_version"], reservation["plan_version"])
        self.assertEqual(self.post(path, {"username": "replace"}).status_code, 400)

    @override_settings(CAF_FORM_URL="http://127.0.0.1:18110/caf/new", CAF_FORM_ALLOWED_ORIGINS=["http://127.0.0.1:18110"], CAF_DEMO_LOCAL_HTTP=True)
    def test_directory_customer_id_and_same_caf_form_entry(self):
        self.provision(self.bundle())
        self.client.force_login(self.actor)
        page = self.client.get(f"/companies/{self.tenant.company_id}/users/?account_id=1000000123")
        self.assertContains(page, "1000000123")
        self.assertContains(page, "Add customer using CAF form")
        self.assertNotContains(page, 'name="kind" value="subscriber"')
        response = self.client.get(f"/companies/{self.tenant.company_id}/onboard/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://127.0.0.1:18110/caf/new?companyId=company-a&returnTo="))
        Membership.objects.filter(user=self.actor).update(role="viewer")
        self.assertEqual(self.client.get(f"/companies/{self.tenant.company_id}/onboard/").status_code, 403)


@skipUnless(connection.vendor == "mysql", "MariaDB row-lock concurrency check")
@override_settings(**PRODUCTION_FIXTURE)
class CAFConcurrentProvisioningTests(TransactionTestCase):
    setUp = CAFProvisioningTests.setUp
    post = CAFProvisioningTests.post
    reserve = CAFProvisioningTests.reserve
    bundle = CAFProvisioningTests.bundle

    def test_concurrent_deliveries_accept_only_one_credential_and_service(self):
        original = self.bundle()
        other = copy.deepcopy(original)
        other["provisioning_request_id"] = str(uuid.uuid4())

        def deliver(body):
            close_old_connections()
            try:
                return Client().post("/api/integrations/ecaf/v2/provisionings", data=json.dumps(body),
                    content_type="application/json", secure=True, HTTP_AUTHORIZATION="Bearer " + self.secret,
                    HTTP_IDEMPOTENCY_KEY=body["provisioning_request_id"]).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(deliver, [original, other]))
        self.assertEqual(sorted(statuses), [202, 409])
        self.assertEqual(Subscriber.objects.count(), 1)
        self.assertEqual(CAFDeliveryReceipt.objects.filter(operation="provisionings-v2").count(), 1)
        self.assertTrue(CAFServiceRequest.objects.get().credential_accepted)
