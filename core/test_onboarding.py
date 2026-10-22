from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import AuditEvent, Membership, NAS, Plan, Subscriber, Tenant


class CompanyOnboardingTests(TestCase):
    companies = ["infolink-broadband=Infolink Broadband", "northnet=NorthNet", "vm-net=VM Net"]

    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("panel-admin", password="existing-login-password")

    def onboard(self, **kwargs):
        arguments = [argument for company in self.companies for argument in ["--company", company]]
        call_command("onboard_companies", *arguments, owner="panel-admin",
                     stdout=StringIO(), **kwargs)

    def test_preview_does_not_write(self):
        self.onboard()
        self.assertFalse(Tenant.objects.exists())
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_apply_creates_three_companies_and_is_idempotent(self):
        self.onboard(apply=True)
        self.onboard(apply=True)
        self.assertEqual(set(Tenant.objects.values_list("name", flat=True)),
                         {"Infolink Broadband", "NorthNet", "VM Net"})
        self.assertEqual(Membership.objects.filter(user=self.owner, role="owner").count(), 3)
        self.assertEqual(AuditEvent.objects.filter(action="tenant.create").count(), 3)
        self.assertEqual(AuditEvent.objects.filter(action="membership.owner_grant").count(), 3)
        self.assertFalse(Plan.objects.exists())
        self.assertFalse(Subscriber.objects.exists())
        self.assertFalse(NAS.objects.exists())
        self.owner.refresh_from_db()
        self.assertTrue(check_password("existing-login-password", self.owner.password))

    def test_inactive_or_unprivileged_owner_cannot_onboard(self):
        for updates in [{"is_active": False}, {"is_active": True, "is_superuser": False}]:
            get_user_model().objects.filter(pk=self.owner.pk).update(**updates)
            with self.assertRaises(CommandError):
                self.onboard(apply=True)
            self.assertFalse(Tenant.objects.exists())

    def test_conflicts_do_not_change_existing_data_or_create_other_companies(self):
        existing = Tenant.objects.create(slug="northnet", name="Existing unrelated company")
        with self.assertRaises(CommandError):
            self.onboard(apply=True)
        self.assertEqual(Tenant.objects.count(), 1)
        self.assertFalse(AuditEvent.objects.exists())
        existing.name = "NorthNet"
        existing.active = False
        existing.save()
        with self.assertRaises(CommandError):
            self.onboard(apply=True)
        existing.active = True
        existing.save()
        Membership.objects.create(tenant=existing, user=self.owner, role="viewer")
        with self.assertRaises(CommandError):
            self.onboard(apply=True)
        self.assertEqual(Membership.objects.get().role, "viewer")
        self.assertEqual(Tenant.objects.count(), 1)

    def test_audit_failure_rolls_back_all_companies(self):
        with patch("core.management.commands.onboard_companies.AuditEvent.objects.create", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.onboard(apply=True)
        self.assertFalse(Tenant.objects.exists())
        self.assertFalse(Membership.objects.exists())

    def test_invalid_and_duplicate_company_slugs_rejected(self):
        for companies in [["invalid slug=Name"], ["valid="], ["missing-name"],
                          ["same=One", "same=Two"], ["Upper=Name"]]:
            with self.subTest(companies=companies), self.assertRaises(CommandError):
                arguments = [argument for company in companies for argument in ["--company", company]]
                call_command("onboard_companies", *arguments, owner="panel-admin",
                             apply=True, stdout=StringIO())
        self.assertFalse(Tenant.objects.exists())
