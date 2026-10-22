"""Company-owner settings, with one-time issued keys and write-only peer keys."""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_GET

from .caf_catalog import authenticate, issue_token, _json, publish_plan
from .caf_connections import (GRANTS, ConnectionTestError, fingerprint, open_token, reset_test,
                              seal_token, staged_ready, test_remote, validate_origin)
from .forms import DashboardFormMixin
from .models import (AuditEvent, CAFCompanyBinding, CAFConnection, CAFFranchiseBinding,
                     CAFServiceToken, Membership, Plan, Tenant)
from .services import require_membership


class ConnectionForm(DashboardFormMixin, forms.Form):
    source = forms.SlugField(max_length=64, label="Agreed CAF source")
    caf_company_id = forms.CharField(max_length=128, label="Exact CAF company ID")
    origin = forms.CharField(max_length=256, label="CAF HTTPS origin", validators=[validate_origin])
    caf_read_key = forms.CharField(required=False, strip=False, max_length=256, label="CAF-issued read API key",
                                   widget=forms.PasswordInput(render_value=False))
    clear_key = forms.BooleanField(required=False, label="Remove saved CAF key and disable staged delivery")


class FranchiseForm(DashboardFormMixin, forms.Form):
    caf_franchise_id = forms.CharField(max_length=128, label="Exact CAF franchise ID")
    name = forms.CharField(max_length=160, label="Mapping label")


class IssueForm(DashboardFormMixin, forms.Form):
    expires_days = forms.IntegerField(min_value=1, max_value=90, initial=30, label="Key validity (days)")
    plans_read = forms.BooleanField(required=False, initial=True)
    reservations_write = forms.BooleanField(required=False)
    provisionings_write = forms.BooleanField(required=False)
    receipts_read = forms.BooleanField(required=False)

    def clean(self):
        values = super().clean()
        if not any(values.get(grant) for grant in GRANTS):
            raise ValidationError("Select at least one operation grant.")
        return values


def _audit(request, tenant, target, action, outcome):
    AuditEvent.objects.create(tenant=tenant, actor=request.user, target_id=target,
                              action="caf.connection." + action, outcome=outcome)


@login_required
@never_cache
@sensitive_post_parameters("caf_read_key")
@sensitive_variables()
@require_http_methods(["GET", "POST"])
def connection_settings(request, company_id):
    tenant = get_object_or_404(Tenant, company_id=company_id, active=True)
    membership = require_membership(request.user, tenant.pk, write=True)
    if membership.role != Membership.Role.OWNER:
        raise PermissionDenied
    binding = CAFCompanyBinding.objects.filter(tenant=tenant).order_by("id").first()
    connection = CAFConnection.objects.filter(binding=binding).first() if binding else None
    action = request.POST.get("action") if request.method == "POST" else None
    connection_form = ConnectionForm(request.POST if action == "save" else None, initial={
        "source": binding.source if binding else "caf-portal",
        "caf_company_id": binding.caf_company_id if binding else "",
        "origin": connection.origin if connection else "",
    })
    franchise_form = FranchiseForm(request.POST if action == "map_franchise" else None)
    issue_form = IssueForm(request.POST if action == "issue" else None)
    notice, issued_key, error = "", "", ""
    try:
        if action == "test":
            if not connection:
                raise ValidationError("Save the connection and franchise mapping first.")
            expected = fingerprint(connection)
            try:
                verified = test_remote(connection)
                outcome = "ok"
            except (ConnectionTestError, ValidationError) as exc:
                verified = ""
                outcome = str(exc) if isinstance(exc, ConnectionTestError) else "caf_configuration_failed"
            with transaction.atomic():
                Tenant.objects.select_for_update().get(pk=tenant.pk)
                connection.refresh_from_db()
                if expected != fingerprint(connection) or (verified and verified != expected):
                    raise ValidationError("Configuration changed during testing. Test again.")
                reset_test(connection)
                connection.tested_fingerprint = verified
                connection.tested_at = timezone.now()
                connection.test_result = outcome
                connection.save()
                _audit(request, tenant, binding.pk, "test", outcome)
            notice = "CAF company and franchise scopes verified. Delivery remains disabled; enable it separately." if verified else "Connection test failed: " + outcome
        elif action:
            with transaction.atomic():
                Tenant.objects.select_for_update().get(pk=tenant.pk)
                # Refresh after the tenant lock to serialize concurrent saves, keys and enables.
                binding = CAFCompanyBinding.objects.filter(tenant=tenant).order_by("id").first()
                connection = CAFConnection.objects.filter(binding=binding).first() if binding else None
                if action == "save" and connection_form.is_valid():
                    data = connection_form.cleaned_data
                    if binding and (binding.source != data["source"] or binding.caf_company_id != data["caf_company_id"]):
                        raise ValidationError("Company/source identity is immutable. Resolve mapping conflicts with the administrator.")
                    if data["clear_key"] and data["caf_read_key"]:
                        raise ValidationError("Choose either replacement or removal of the key.")
                    if not binding:
                        binding = CAFCompanyBinding.objects.create(tenant=tenant, source=data["source"], caf_company_id=data["caf_company_id"])
                    if not connection:
                        connection = CAFConnection(binding=binding, origin=data["origin"])
                    if connection.origin != data["origin"] and connection.token_ciphertext and not (data["caf_read_key"] or data["clear_key"]):
                        raise ValidationError("Changing origin requires a replacement key or removal of the old key.")
                    connection.origin = data["origin"]
                    if data["caf_read_key"]:
                        connection.encryption_key_id, connection.token_ciphertext = seal_token(binding, connection.origin, data["caf_read_key"])
                    if data["clear_key"]:
                        connection.encryption_key_id, connection.token_ciphertext = "", ""
                    reset_test(connection)
                    connection.save()
                    _audit(request, tenant, binding.pk, "save", "disabled")
                    notice = "Connection saved. Staged delivery is disabled until tested and explicitly enabled."
                elif action == "map_franchise" and franchise_form.is_valid():
                    if not connection:
                        raise ValidationError("Save a company connection first.")
                    data = franchise_form.cleaned_data
                    record, created = CAFFranchiseBinding.objects.get_or_create(company=binding,
                        caf_franchise_id=data["caf_franchise_id"], defaults={"name": data["name"]})
                    if not created:
                        raise ValidationError("This exact franchise mapping already exists; its identity was preserved.")
                    reset_test(connection)
                    connection.save()
                    _audit(request, tenant, record.pk, "franchise_map", "saved")
                    notice = "Franchise mapped. Test again before enabling delivery."
                elif action == "disable_franchise":
                    if not connection:
                        raise ValidationError("Connection required.")
                    record = get_object_or_404(CAFFranchiseBinding, company=binding, pk=request.POST.get("franchise_id"))
                    record.active = False
                    record.save(update_fields=["active"])
                    reset_test(connection)
                    connection.save()
                    _audit(request, tenant, record.pk, "franchise_disable", "disabled")
                    notice = "Mapping disabled; no identity was deleted or reassigned."
                elif action == "issue" and issue_form.is_valid():
                    if not binding or not binding.active:
                        raise ValidationError("An active company connection is required.")
                    data = issue_form.cleaned_data
                    token, issued_key = issue_token(binding, expires_at=timezone.now() + timedelta(days=data["expires_days"]),
                                                    plans_read=data["plans_read"])
                    for grant in GRANTS[1:]:
                        setattr(token, grant, data[grant])
                    token.save(update_fields=list(GRANTS[1:]))
                    _audit(request, tenant, token.pk, "key_issue", "issued")
                    notice = "Copy this Radius-issued key into CAF backend settings now. It cannot be retrieved again."
                elif action == "revoke":
                    token = get_object_or_404(CAFServiceToken, binding=binding, pk=request.POST.get("token_id"))
                    token.active = False
                    token.save(update_fields=["active"])
                    _audit(request, tenant, token.pk, "key_revoke", "revoked")
                    notice = "Radius-issued key revoked. Other issued keys are unchanged."
                elif action == "disable":
                    if connection:
                        connection.staged_enabled = False
                        connection.save(update_fields=["staged_enabled", "updated_at"])
                        _audit(request, tenant, binding.pk, "disable", "disabled")
                    notice = "New staged writes disabled. Existing accepted services and receipts are preserved."
                elif action == "enable":
                    if not settings.CAF_PRODUCTION_STAGED_ENABLED or not settings.CAF_PROVISIONING_ENABLED:
                        raise ValidationError("Server production-STAGED and provisioning gates must be enabled by the administrator.")
                    if not connection or connection.test_result != "ok" or connection.tested_fingerprint != fingerprint(connection):
                        raise ValidationError("Test the current company, franchise and key configuration first.")
                    if not connection.tested_at or timezone.now() - connection.tested_at > timedelta(minutes=30):
                        raise ValidationError("Connection test is older than 30 minutes. Test again before enabling.")
                    open_token(connection)  # Fail closed if the encryption key was removed.
                    try:
                        key = bytes.fromhex(settings.CAF_FINGERPRINT_KEYS[settings.CAF_FINGERPRINT_KEY_ID])
                        if len(key) < 32:
                            raise ValueError
                    except (KeyError, TypeError, ValueError):
                        raise ValidationError("Configure the server fingerprint key ring before enabling delivery.") from None
                    if not binding.active:
                        raise ValidationError("The company binding is disabled.")
                    connection.staged_enabled = True
                    connection.save(update_fields=["staged_enabled", "updated_at"])
                    _audit(request, tenant, binding.pk, "enable", "staged_only")
                    notice = "Staged provisioning enabled for this company. Internet activation remains disabled."
                elif action == "publish":
                    plan = get_object_or_404(Plan, tenant=tenant, pk=request.POST.get("plan_id"))
                    try:
                        seconds = int(request.POST.get("duration_seconds", ""))
                    except ValueError:
                        raise ValidationError("Enter a positive whole duration in seconds.") from None
                    publish_plan(actor=request.user, plan_id=plan.pk, duration_seconds=seconds,
                                 active=request.POST.get("withdraw") != "true")
                    notice = "Plan publication updated."
                elif action not in {"save", "map_franchise", "issue"}:
                    raise ValidationError("Unknown settings action.")
    except ValidationError as exc:
        error = " ".join(exc.messages)
    except (IntegrityError, ValueError):
        error = "The operation conflicts with existing settings or contains an invalid identifier. No change was saved."
    # Re-query after any rollback. Never put ciphertext or peer key into template context.
    binding = CAFCompanyBinding.objects.filter(tenant=tenant).order_by("id").first()
    connection = CAFConnection.objects.filter(binding=binding).first() if binding else None
    status = {"configured": bool(connection), "key_saved": bool(connection and connection.token_ciphertext),
              "enabled": bool(binding and staged_ready(binding)), "test_result": connection.test_result if connection else "not_tested",
              "tested_at": connection.tested_at if connection else None}
    return render(request, "caf_settings.html", {"tenant": tenant, "membership": membership,
        "memberships": Membership.objects.select_related("tenant").filter(user=request.user, tenant__active=True),
        "section": "caf-settings", "connection_form": connection_form, "franchise_form": franchise_form,
        "issue_form": issue_form, "status": status, "notice": notice, "error": error,
        "issued_key": issued_key, "binding": binding,
        "franchises": CAFFranchiseBinding.objects.filter(company=binding),
        "tokens": CAFServiceToken.objects.filter(binding=binding).defer("secret_digest").order_by("-created_at"),
        "plans": Plan.objects.filter(tenant=tenant).select_related("cafplanpublication"),
        "server_staged": settings.CAF_PRODUCTION_STAGED_ENABLED,
    })


@require_GET
def connection_status(request):
    token, error = authenticate(request, "plans_read", enabled=settings.CAF_CATALOG_ENABLED)
    if error is not None:
        return error
    binding = token.binding
    return _json({"schema_version": "1.0", "source": binding.source, "company_ref": {"id": binding.caf_company_id},
        "radius_company_id": str(binding.tenant.company_id),
        "franchise_refs": [{"id": value} for value in CAFFranchiseBinding.objects.filter(company=binding, active=True)
                           .order_by("caf_franchise_id").values_list("caf_franchise_id", flat=True)],
        "mode": "staged", "staged_enabled": bool(staged_ready(binding)),
        "grants": {grant: getattr(token, grant) for grant in GRANTS},
        "token_expires_at": token.expires_at.isoformat()})
