"""CAF service writes: durable, idempotent and disabled until explicitly configured."""
import hashlib
import hmac
import json
import re
import uuid
from datetime import timedelta
from pathlib import Path

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, ValidationError as SchemaError
from referencing import Registry, Resource
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables

from .caf_catalog import _error, _json, authenticate
from .models import (CAFDeliveryReceipt, CAFCustomerLink, CAFFranchiseBinding, CAFPlanPublication,
                     CAFReservation, CAFServiceRequest, CAFUsernameClaim, NAS, Subscriber, Tenant)

ROOT = Path(__file__).parent / "caf_schemas"
APPROVAL = json.loads((ROOT / "ecaf-event.schema.json").read_text())
PROVISIONING = json.loads((ROOT / "ecaf-provisioning.schema.json").read_text())
REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in [APPROVAL, PROVISIONING])
UUID = {"type": "string", "format": "uuid"}
REFERENCE = {"$ref": APPROVAL["$id"] + "#/$defs/reference"}
RESERVE = {"type": "object", "additionalProperties": False,
           "required": ["customer_id", "service_request_id", "username", "plan_id", "plan_version", "company_ref", "franchise_ref"],
           "properties": {"customer_id": APPROVAL["properties"]["customer_id"], "service_request_id": UUID,
                          "username": PROVISIONING["properties"]["service"]["properties"]["username"],
                          "plan_id": UUID, "plan_version": {"type": "integer", "minimum": 1, "maximum": 9007199254740991},
                          "company_ref": REFERENCE, "franchise_ref": REFERENCE}}
V2 = {"type": "object", "additionalProperties": False,
      "required": ["schema_version", "provisioning_request_id", "supersedes_request_id", "approval", "service"],
      "properties": {"schema_version": {"const": "2.0"}, "provisioning_request_id": UUID,
                     "supersedes_request_id": {"oneOf": [UUID, {"type": "null"}]},
                     "approval": {"$ref": APPROVAL["$id"]}, "service": PROVISIONING["properties"]["service"]}}


class Rejected(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def _reject(code, status=409):
    raise Rejected(code, status)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _body(request, schema):
    if request.content_type != "application/json":
        _reject("json_required", 400)
    try:
        if len(request.body) > 65536:
            _reject("payload_too_large", 413)
        data = json.loads(request.body, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker()).validate(data)
        rfc8785.dumps(data)
        return data
    except (ValueError, UnicodeError, SchemaError, RequestDataTooBig, RecursionError):
        _reject("invalid_payload", 400)


def _key(request):
    try:
        return uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except ValueError:
        _reject("invalid_idempotency_key", 400)


@sensitive_variables()
def _fingerprint(operation, data, key_id=None):
    key_id = key_id or settings.CAF_FINGERPRINT_KEY_ID
    try:
        key = bytes.fromhex(settings.CAF_FINGERPRINT_KEYS[key_id])
        if len(key) < 32:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        _reject("fingerprint_key_unavailable", 503)
    return hmac.new(key, operation.encode() + b"\0" + rfc8785.dumps(data), hashlib.sha256).hexdigest()


def _existing(token, operation, delivery_id, data):
    receipt = CAFDeliveryReceipt.objects.filter(source=token.binding.source, operation=operation, delivery_id=delivery_id).first()
    if receipt:
        if receipt.binding_id != token.binding_id or not hmac.compare_digest(receipt.fingerprint, _fingerprint(operation, data, receipt.key_id)):
            _reject("replay_conflict")
    return receipt


def _save(token, operation, delivery_id, data, response, status, *, service=None, binding_fingerprint="", predecessor=None):
    return CAFDeliveryReceipt.objects.create(tenant_id=token.binding.tenant_id, source=token.binding.source,
        binding=token.binding, operation=operation, delivery_id=delivery_id,
        fingerprint=_fingerprint(operation, data), key_id=settings.CAF_FINGERPRINT_KEY_ID,
        response=response, http_status=status, request=service,
        binding_fingerprint=binding_fingerprint, predecessor=predecessor)


def _scope(token, company, franchise):
    if company["id"] != token.binding.caf_company_id:
        _reject("company_binding_conflict", 422)
    mapping = CAFFranchiseBinding.objects.filter(company=token.binding, caf_franchise_id=franchise["id"], active=True).first()
    if not mapping:
        _reject("franchise_mapping_required", 422)
    return mapping


def _publication(service):
    entry = CAFPlanPublication.objects.select_related("plan").filter(plan=service.plan, active=True).first()
    if not entry or entry.version != service.plan_version or entry.plan.tenant_id != service.tenant_id or (
        entry.name, entry.upload_kbps, entry.download_kbps) != (entry.plan.name, entry.plan.upload_kbps, entry.plan.download_kbps):
        _reject("plan_changed")
    return entry


def _reservation_json(reservation):
    s = reservation.request
    return {"source_id": s.source, "customer_id": s.customer_id, "company_ref": {"id": s.binding.caf_company_id},
            "franchise_ref": {"id": s.franchise.caf_franchise_id}, "radius_company_id": str(s.tenant.company_id),
            "radius_franchise_id": str(s.franchise.franchise_id), "reservation_id": str(reservation.pk),
            "service_request_id": str(s.service_request_id), "username": s.username, "plan_id": str(s.plan_id),
            "plan_version": s.plan_version, "expires_at": reservation.expires_at.isoformat().replace("+00:00", "Z")}


def _reserve(token, delivery_id, data):
    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=token.binding.tenant_id)
        old = _existing(token, "reservations", delivery_id, data)
        if old:
            return _json(old.response, old.http_status)
        franchise = _scope(token, data["company_ref"], data["franchise_ref"])
        service = CAFServiceRequest.objects.filter(source=token.binding.source, service_request_id=data["service_request_id"]).first()
        if service and (service.binding_id != token.binding_id or service.customer_id != data["customer_id"] or
                        service.franchise_id != franchise.pk or service.username != data["username"] or
                        service.plan_id != uuid.UUID(data["plan_id"]) or service.plan_version != data["plan_version"]):
            _reject("reservation_binding_conflict")
        if service and service.credential_accepted:
            _reject("service_already_provisioned")
        if not service:
            if not CAFPlanPublication.objects.filter(plan_id=data["plan_id"], plan__tenant=token.binding.tenant).exists():
                _reject("plan_not_found", 404)
            service = CAFServiceRequest.objects.create(tenant=token.binding.tenant, binding=token.binding,
                source=token.binding.source, franchise=franchise, customer_id=data["customer_id"],
                service_request_id=data["service_request_id"], username=data["username"], plan_id=data["plan_id"], plan_version=data["plan_version"])
        _publication(service)
        if Subscriber.objects.filter(tenant=service.tenant, username__iexact=service.username).exists():
            _reject("username_unavailable")
        claim = CAFUsernameClaim.objects.filter(tenant=service.tenant, normalized_username=service.username.lower()).select_related("request").first()
        if claim and claim.request_id != service.pk:
            if claim.request.credential_accepted or CAFReservation.objects.filter(request=claim.request, expires_at__gt=timezone.now()).exists():
                _reject("username_unavailable")
            claim.delete()
            claim = None
        if claim is None:
            CAFUsernameClaim.objects.create(tenant=service.tenant, normalized_username=service.username.lower(), request=service)
        reservation = CAFReservation.objects.filter(request=service, expires_at__gt=timezone.now()).order_by("-expires_at").first()
        if not reservation:
            reservation = CAFReservation.objects.create(request=service, expires_at=timezone.now() + timedelta(minutes=15))
        response = _reservation_json(reservation)
        _save(token, "reservations", delivery_id, data, response, 201, service=service)
        return _json(response, 201)


def _renew(token, delivery_id, data):
    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=token.binding.tenant_id)
        prior = _existing(token, "reservation-renewal", delivery_id, data)
        if prior:
            return _json(prior.response, prior.http_status)
        reservation = CAFReservation.objects.select_related("request__franchise", "request__binding", "request__tenant").filter(
            pk=data["reservation_id"], request__binding=token.binding).first()
        if not reservation:
            _reject("reservation_not_found", 404)
        service = reservation.request
        if not service.franchise.active or service.credential_accepted:
            _reject("replacement_not_allowed")
        _publication(service)
        if Subscriber.objects.filter(tenant=service.tenant, username__iexact=service.username).exists():
            _reject("username_unavailable")
        claim = CAFUsernameClaim.objects.filter(tenant=service.tenant, normalized_username=service.username.lower()).select_related("request").first()
        if claim and claim.request_id != service.pk:
            if claim.request.credential_accepted or CAFReservation.objects.filter(request=claim.request, expires_at__gt=timezone.now()).exists():
                _reject("username_unavailable")
            claim.delete()
            claim = None
        if claim is None:
            CAFUsernameClaim.objects.create(tenant=service.tenant, normalized_username=service.username.lower(), request=service)
        reservation.expires_at = timezone.now() + timedelta(minutes=15)
        reservation.save(update_fields=["expires_at"])
        response = _reservation_json(reservation)
        _save(token, "reservation-renewal", delivery_id, data, response, 200, service=service)
        return _json(response)


def _receipt_json(token, service, delivery_id, event_id, *, accepted, error=None):
    return {"schema_version": "2.0", "source_id": service.source, "customer_id": service.customer_id,
            "company_ref": {"id": token.binding.caf_company_id}, "franchise_ref": {"id": service.franchise.caf_franchise_id},
            "radius_company_id": str(token.binding.tenant.company_id), "radius_franchise_id": str(service.franchise.franchise_id),
            "event_id": str(event_id), "provisioning_request_id": str(delivery_id), "service_request_id": str(service.service_request_id),
            "receipt_version": 1, "receipt_status": "blocked" if accepted else "failed", "credential_accepted": accepted,
            "service_id": str(service.subscriber_id) if service.subscriber_id else None,
            "service_status": "pending_service_setup" if accepted else "blocked", "error": error}


def _identity(approval):
    p = approval["profile"]
    return {"name": p["name"], "mobile": p.get("mobile"), "email": p.get("email")}


@sensitive_variables()
def _provision(token, delivery_id, data):
    approval, supplied = data["approval"], data["service"]
    if uuid.UUID(data["provisioning_request_id"]) != delivery_id:
        _reject("idempotency_key_mismatch", 400)
    password = supplied["initial_password"]
    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=token.binding.tenant_id)
        previous = _existing(token, "provisionings-v2", delivery_id, data)
        if previous:
            return _json(previous.response, previous.http_status)
        if len(password.encode("utf-8")) > 128:
            _reject("invalid_password", 400)
        try:
            validate_password(password)
        except ValidationError:
            _reject("invalid_password", 400)
        franchise = _scope(token, approval["company_ref"], approval["franchise_ref"])
        service = CAFServiceRequest.objects.select_for_update().filter(source=token.binding.source, service_request_id=supplied["service_request_id"]).first()
        if not service or service.binding_id != token.binding_id or service.franchise_id != franchise.pk or service.customer_id != approval["customer_id"]:
            _reject("service_binding_conflict", 422)
        if service.username != supplied["username"] or service.plan_id != uuid.UUID(supplied["plan_id"]):
            _reject("reservation_binding_conflict")
        if service.credential_accepted:
            _reject("service_already_provisioned")
        publication = _publication(service)
        immutable = {"source": service.source, "binding": str(service.binding_id), "franchise": str(service.franchise_id),
                     "approval": approval, "service": {k: v for k, v in supplied.items() if k != "reservation_id"}, "plan_version": service.plan_version}
        parent = None
        if data["supersedes_request_id"]:
            parent = CAFDeliveryReceipt.objects.select_for_update().filter(source=service.source, operation="provisionings-v2", delivery_id=data["supersedes_request_id"]).first()
            if not parent:
                _reject("receipt_reconciliation_required")
            if parent.request_id != service.pk or parent.response.get("credential_accepted") is not False or (parent.response.get("error") or {}).get("code") != "reservation_expired" or CAFDeliveryReceipt.objects.filter(predecessor=parent).exists():
                _reject("replacement_not_allowed")
            if not hmac.compare_digest(parent.binding_fingerprint, _fingerprint("immutable-v2", immutable, parent.key_id)):
                _reject("replacement_binding_conflict")
        elif CAFDeliveryReceipt.objects.filter(request=service, operation="provisionings-v2").exists():
            _reject("replacement_not_allowed")
        reservation = CAFReservation.objects.filter(pk=supplied["reservation_id"], request=service).first()
        if not reservation:
            _reject("reservation_binding_conflict")
        if reservation.expires_at <= timezone.now() or not CAFUsernameClaim.objects.filter(request=service, normalized_username=service.username.lower()).exists():
            response = _receipt_json(token, service, delivery_id, approval["event_id"], accepted=False,
                error={"code": "reservation_expired", "message": "Renew reservation and replace delivery", "retryable": False})
            _save(token, "provisionings-v2", delivery_id, data, response, 409, service=service,
                  binding_fingerprint=_fingerprint("immutable-v2", immutable), predecessor=parent)
            return _json(response, 409)
        link = CAFCustomerLink.objects.select_for_update().filter(source=service.source, customer_id=service.customer_id).first()
        if link and (link.binding_id != service.binding_id or link.franchise_id != service.franchise_id):
            _reject("customer_binding_conflict")
        identity = _identity(approval)
        if link and link.profile_version == approval["customer_version"] and link.profile != identity:
            _reject("profile_version_conflict")
        if not link:
            link = CAFCustomerLink.objects.create(tenant=service.tenant, source=service.source, binding=service.binding,
                franchise=service.franchise, customer_id=service.customer_id, profile_version=approval["customer_version"], profile=identity)
        elif approval["customer_version"] > link.profile_version:
            link.profile_version, link.profile = approval["customer_version"], identity
            link.save(update_fields=["profile_version", "profile"])
        # Receiving an approved envelope NEVER grants activation. Its exact CAF
        # authorization must be verified in a separate, explicit operational step.
        subscriber = Subscriber.objects.create(tenant=service.tenant, username=service.username, plan=service.plan,
            password_hash=make_password(password, hasher="pbkdf2_sha256"), status=Subscriber.Status.SUSPENDED, expires_at=timezone.now())
        service.subscriber, service.customer_link = subscriber, link
        service.credential_accepted, service.state = True, "awaiting_authorization"
        service.approval_event_id = uuid.UUID(approval["event_id"])
        service.save()
        response = _receipt_json(token, service, delivery_id, approval["event_id"], accepted=True,
            error={"code": "activation_authorization_required", "message": "Credential accepted; service remains disabled pending authorization", "retryable": False})
        if getattr(settings, "CAF_DEMO_AUTO_ACTIVATE", False):
            # This explicit demo shortcut never runs against MariaDB/live NAS.
            # It demonstrates approved provisioning, not distributed withdrawal fencing.
            if connection.vendor != "sqlite" or not getattr(settings, "CAF_DEMO_LOCAL_HTTP", False) or NAS.objects.filter(enabled=True).exists():
                _reject("demo_activation_not_isolated", 503)
            anchor = timezone.now()
            subscriber.status = Subscriber.Status.ACTIVE
            subscriber.expires_at = anchor + timedelta(seconds=publication.duration_seconds)
            subscriber.save(update_fields=["status", "expires_at"])
            service.state, service.activated_at = "demo_active", anchor
            service.save(update_fields=["state", "activated_at"])
            response.update(receipt_status="applied", service_status="active", error=None)
        _save(token, "provisionings-v2", delivery_id, data, response, 202, service=service,
              binding_fingerprint=_fingerprint("immutable-v2", immutable), predecessor=parent)
        return _json(response, 202)


@csrf_exempt
@sensitive_variables()
def reservations(request):
    return _dispatch(request, "reservations_write", _reserve, RESERVE)


@csrf_exempt
@sensitive_variables()
def provisionings(request):
    return _dispatch(request, "provisionings_write", _provision, V2)


@csrf_exempt
def renew_reservation(request, reservation_id):
    # No mutable binding fields in a renewal. The route ID is fingerprint-bound.
    def handler(token, delivery_id, body):
        return _renew(token, delivery_id, {"reservation_id": str(reservation_id)})
    return _dispatch(request, "reservations_write", handler, {"type": "object", "additionalProperties": False})


@sensitive_variables()
def _dispatch(request, grant, handler, schema):
    try:
        if request.method != "POST":
            response = _error("method_not_allowed", 405, "Use POST")
            response["Allow"] = "POST"
            return response
        token, error = authenticate(request, grant, enabled=settings.CAF_PROVISIONING_ENABLED)
        if error is not None:
            return error
        return handler(token, _key(request), _body(request, schema))
    except Rejected as exc:
        return _error(exc.code, exc.status, "Request requires correction or reconciliation", retryable=exc.status == 503)
    except IntegrityError:
        return _error("concurrent_binding_conflict", 409, "Reconcile the service request before retry")
    except DatabaseError:
        return _error("temporarily_unavailable", 503, "Service storage unavailable", retryable=True)


def receipt(request, delivery_id):
    try:
        if request.method != "GET":
            return _error("method_not_allowed", 405, "Use GET")
        token, error = authenticate(request, "receipts_read", enabled=settings.CAF_PROVISIONING_ENABLED)
        if error is not None:
            return error
        record = CAFDeliveryReceipt.objects.filter(binding=token.binding, operation="provisionings-v2", delivery_id=delivery_id).first()
        return _json(record.response) if record else _error("not_found", 404, "Scoped receipt not found")
    except DatabaseError:
        return _error("temporarily_unavailable", 503, "Service storage unavailable", retryable=True)
