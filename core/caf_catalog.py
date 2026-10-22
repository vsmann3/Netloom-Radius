"""Scoped CAF catalog and shared service authentication. No activation here."""

import hashlib
import re
import secrets
import uuid

from django.conf import settings
from django.core import signing
from django.db import DatabaseError, transaction
from django.db.models import BinaryField, F, Func
from django.http import JsonResponse
from django.utils import timezone

from .models import AuditEvent, CAFPlanPublication, CAFServiceToken, Plan
from .services import require_membership


class ByteString(Func):
    """Compare complete bytes, including trailing spaces, before SQL pagination."""

    output_field = BinaryField()
    arity = 1

    def as_mysql(self, compiler, connection, **extra_context):
        return self.as_sql(compiler, connection, template="CAST(%(expressions)s AS BINARY)", **extra_context)

    def as_sqlite(self, compiler, connection, **extra_context):
        return self.as_sql(compiler, connection, template="CAST(%(expressions)s AS BLOB)", **extra_context)


def issue_token(binding, *, expires_at, plans_read=False):
    if not binding.active or not binding.tenant.active or expires_at <= timezone.now():
        raise ValueError("An active binding and future expiry are required")
    secret = secrets.token_urlsafe(32)
    token = CAFServiceToken.objects.create(
        binding=binding, expires_at=expires_at, plans_read=plans_read,
        secret_digest=hashlib.sha256(secret.encode("ascii")).hexdigest(),
    )
    return token, f"nlcaf_{token.id.hex}.{secret}"


@transaction.atomic
def publish_plan(*, actor, plan_id, duration_seconds, active=True):
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int) or not 1 <= duration_seconds <= 4294967295:
        raise ValueError("Use a positive whole duration in seconds")
    plan = Plan.objects.select_for_update().get(pk=plan_id)
    require_membership(actor, plan.tenant_id, write=True)
    publication = CAFPlanPublication.objects.filter(plan=plan).first()
    values = dict(name=plan.name, upload_kbps=plan.upload_kbps,
                  download_kbps=plan.download_kbps, duration_seconds=duration_seconds, active=active)
    if publication and all(getattr(publication, k) == v for k, v in values.items()):
        return publication
    version = publication.version + 1 if publication else 1
    if version > 9007199254740991:
        raise ValueError("Plan publication version exhausted")
    publication, _ = CAFPlanPublication.objects.update_or_create(plan=plan, defaults={**values, "version": version})
    AuditEvent.objects.create(tenant_id=plan.tenant_id, actor=actor, action="caf.plan.publish",
                              target_id=plan.id, outcome="published" if active else "withdrawn")
    return publication


def _json(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _error(code, status, message, *, retryable=False):
    response = _json({"error": {"code": code, "message": message, "retryable": retryable},
                      "request_id": str(uuid.uuid4())}, status)
    if status == 401:
        response["WWW-Authenticate"] = "Bearer"
    if status == 405:
        response["Allow"] = "GET"
    return response


def plans(request, radius_company_id):
    try:
        return _plans(request, radius_company_id)
    except DatabaseError:
        # Neither driver exceptions nor connection/credential details cross the API.
        return _error("temporarily_unavailable", 503, "Catalog temporarily unavailable", retryable=True)


def authenticate(request, grant, *, enabled):
    if not enabled:
        return None, _error("integration_disabled", 503, "CAF integration is disabled")
    # The proxy must overwrite this header and the web port must be private.
    trusted_https = (request.META.get("REMOTE_ADDR") in settings.CAF_CATALOG_PROXY_IPS
                     and request.headers.get("X-Forwarded-Proto") == "https")
    demo_http = getattr(settings, "CAF_DEMO_LOCAL_HTTP", False) and request.META.get("REMOTE_ADDR") in {"127.0.0.1", "::1"}
    if not request.is_secure() and not trusted_https and not demo_http:
        return None, _error("https_required", 400, "HTTPS is required")
    header = request.headers.get("Authorization", "")
    match = re.fullmatch(r"Bearer nlcaf_([0-9a-f]{32})\.([A-Za-z0-9_-]{43})", header)
    if not match:
        return None, _error("invalid_token", 401, "Valid service authentication required")
    token = CAFServiceToken.objects.select_related("binding__tenant").filter(pk=uuid.UUID(hex=match[1])).first()
    digest = hashlib.sha256(match[2].encode("ascii")).hexdigest()
    if token is None or not secrets.compare_digest(token.secret_digest, digest) or not token.active or token.expires_at <= timezone.now():
        return None, _error("invalid_token", 401, "Valid service authentication required")
    binding = token.binding
    if not binding.active or not binding.tenant.active:
        return None, _error("invalid_token", 401, "Valid service authentication required")
    if not getattr(token, grant):
        return None, _error("scope_denied", 403, "Required service operation grant missing")
    window = int(timezone.now().timestamp()) // 60
    with transaction.atomic():
        quota = CAFServiceToken.objects.select_for_update().get(pk=token.pk)
        if quota.rate_window != window:
            quota.rate_window, quota.rate_count = window, 0
        if quota.rate_count >= 60:
            response = _error("rate_limited", 429, "Service token request limit reached", retryable=True)
            response["Retry-After"] = str(60 - int(timezone.now().timestamp()) % 60)
            return None, response
        quota.rate_count += 1
        quota.save(update_fields=["rate_window", "rate_count"])
    return token, None


def _plans(request, radius_company_id):
    if request.method != "GET":
        return _error("method_not_allowed", 405, "Use GET")
    token, error = authenticate(request, "plans_read", enabled=settings.CAF_CATALOG_ENABLED)
    if error is not None:
        return error
    binding = token.binding
    company_id = str(binding.tenant.company_id)
    if radius_company_id != company_id:
        return _error("not_found", 404, "Scoped company not found")
    if set(request.GET) - {"cursor", "limit"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        return _error("invalid_query", 400, "Only one cursor and limit are supported")
    raw_limit = request.GET.get("limit", "100")
    if not re.fullmatch(r"[1-9][0-9]{0,2}", raw_limit) or not 1 <= int(raw_limit) <= 100:
        return _error("invalid_limit", 400, "limit must be between 1 and 100")
    limit = int(raw_limit)
    after = None
    cursor = request.GET.get("cursor")
    if cursor is not None:
        if len(cursor) > 2048:
            return _error("invalid_cursor", 400, "Invalid catalog cursor")
        try:
            data = signing.loads(cursor, salt="caf-plans-v1", max_age=900)
            if data["binding"] != str(binding.pk) or data["token"] != str(token.pk) or data["company"] != company_id:
                raise ValueError
            after = uuid.UUID(data["after"])
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            return _error("invalid_cursor", 400, "Invalid or expired catalog cursor")
    # Changed live plan fields invalidate publication until deliberately republished.
    records = CAFPlanPublication.objects.alias(_name_bytes=ByteString(F("name"))).filter(
        plan__tenant=binding.tenant, active=True,
        _name_bytes=ByteString(F("plan__name")),
        upload_kbps=F("plan__upload_kbps"), download_kbps=F("plan__download_kbps"),
    ).order_by("plan_id")
    if after:
        records = records.filter(plan_id__gt=after)
    rows = list(records[:limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = signing.dumps({"binding": str(binding.pk), "token": str(token.pk),
                                 "company": company_id, "after": str(rows[-1].plan_id)},
                                salt="caf-plans-v1", compress=True) if has_more else None
    return _json({"items": [{"plan_id": str(p.plan_id), "radius_company_id": company_id,
                             "name": p.name, "version": p.version, "active": True,
                             "download_kbps": p.download_kbps, "upload_kbps": p.upload_kbps,
                             "validity": {"duration_seconds": p.duration_seconds, "starts_at": "activation"}}
                            for p in rows], "next_cursor": next_cursor, "has_more": has_more})
