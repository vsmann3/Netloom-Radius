"""Owner-managed reciprocal API configuration; no activation or broad sync."""
import hashlib
import http.client
import json
import re
import ssl
from urllib.parse import quote, urlencode, urlsplit

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.debug import sensitive_variables

from .models import CAFFranchiseBinding

GRANTS = ("plans_read", "reservations_write", "provisionings_write", "receipts_read")


def validate_origin(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValidationError("Use a valid HTTPS origin.") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or value not in settings.CAF_API_ALLOWED_ORIGINS):
        raise ValidationError("Use an exact administrator-allowed HTTPS CAF origin, without a path or trailing slash.")
    try:
        parsed.port
        value.encode("ascii")
    except (ValueError, UnicodeError):
        raise ValidationError("Use a valid HTTPS origin.") from None
    return value


def _cipher(key_id):
    try:
        return Fernet(settings.CAF_CREDENTIAL_KEYS[key_id].encode("ascii"))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValidationError("CAF credential encryption key is unavailable; contact the administrator.") from None


@sensitive_variables()
def seal_token(binding, origin, token):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{32,256}", token):
        raise ValidationError("Use the CAF-issued read API key (32–256 permitted characters).")
    key_id = settings.CAF_CREDENTIAL_KEY_ID
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key_id):
        raise ValidationError("Configure a valid credential key version identifier.")
    value = json.dumps({"binding": str(binding.pk), "origin": origin, "token": token}).encode()
    return key_id, _cipher(key_id).encrypt(value).decode("ascii")


@sensitive_variables()
def open_token(connection):
    try:
        value = json.loads(_cipher(connection.encryption_key_id).decrypt(connection.token_ciphertext.encode()))
        if value["binding"] != str(connection.binding_id) or value["origin"] != connection.origin:
            raise ValueError
        return value["token"]
    except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError):
        raise ValidationError("CAF credential cannot be read; restore the key or replace the credential.") from None


def fingerprint(connection):
    binding = connection.binding
    value = [str(binding.pk), binding.source, binding.caf_company_id, str(binding.tenant_id), connection.origin,
             connection.encryption_key_id, connection.token_ciphertext,
             list(CAFFranchiseBinding.objects.filter(company=binding).order_by("caf_franchise_id")
                  .values_list("caf_franchise_id", "active"))]
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def staged_ready(binding):
    try:
        connection = binding.connection
    except ObjectDoesNotExist:
        return False
    try:
        validate_origin(connection.origin)
        open_token(connection)
    except ValidationError:
        return False
    return (settings.CAF_PRODUCTION_STAGED_ENABLED and settings.CAF_PROVISIONING_ENABLED and connection.staged_enabled
            and bool(connection.token_ciphertext) and connection.test_result == "ok"
            and connection.tested_fingerprint == fingerprint(connection))


def reset_test(connection):
    connection.staged_enabled = False
    connection.tested_at = None
    connection.tested_fingerprint = ""
    connection.test_result = "configuration_changed"


class ConnectionTestError(Exception):
    """Safe machine code only; never expose remote responses or credentials."""


@sensitive_variables()
def fetch_page(connection, path, cursor=None):
    validate_origin(connection.origin)
    parsed = urlsplit(connection.origin)
    client = None
    target = path + "?" + urlencode({"limit": 100, **({"cursor": cursor} if cursor else {})})
    try:
        context = ssl.create_default_context(cafile=settings.CAF_API_CA_FILE)
        client = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=5, context=context)
        # HTTPSConnection ignores environment proxies and does not follow redirects.
        client.request("GET", target, headers={"Authorization": "Bearer " + open_token(connection), "Accept": "application/json"})
        response = client.getresponse()
        if response.status != 200:
            raise ConnectionTestError("caf_auth_failed" if response.status in (401, 403) else "caf_http_failed")
        if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ConnectionTestError("caf_invalid_response")
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ConnectionTestError("caf_response_too_large")
        result = json.loads(raw)
        if (not isinstance(result, dict) or set(result) != {"items", "has_more", "next_cursor"}
                or not isinstance(result["items"], list) or len(result["items"]) > 100
                or type(result["has_more"]) is not bool
                or (result["next_cursor"] is not None and (not isinstance(result["next_cursor"], str)
                    or not 1 <= len(result["next_cursor"]) <= 2048))
                or result["has_more"] != (result["next_cursor"] is not None)):
            raise ConnectionTestError("caf_invalid_response")
        return result
    except ConnectionTestError:
        raise
    except Exception:
        raise ConnectionTestError("caf_transport_or_configuration_failed") from None
    finally:
        if client:
            client.close()


def directory(connection, path):
    rows, cursors, cursor = [], set(), None
    for _ in range(20):
        page = fetch_page(connection, path, cursor)
        rows.extend(page["items"])
        if not page["has_more"]:
            return rows
        cursor = page["next_cursor"]
        if cursor in cursors or not page["items"]:
            raise ConnectionTestError("caf_invalid_pagination")
        cursors.add(cursor)
    raise ConnectionTestError("caf_directory_limit")


def test_remote(connection):
    validate_origin(connection.origin)
    open_token(connection)  # Fail before DNS/network when the local key ring is unavailable.
    company = connection.binding.caf_company_id
    rows = directory(connection, "/api/integrations/radius/v1/companies")
    if len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get("id") != company or rows[0].get("is_active") is not True:
        raise ConnectionTestError("caf_company_scope_mismatch")
    mapped = set(CAFFranchiseBinding.objects.filter(company=connection.binding, active=True).values_list("caf_franchise_id", flat=True))
    if not mapped:
        raise ConnectionTestError("caf_franchise_mapping_required")
    rows = directory(connection, "/api/integrations/radius/v1/companies/" + quote(company, safe="") + "/franchises")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("company_id") != company or not isinstance(row.get("id"), str)
                or row["id"] in seen):
            raise ConnectionTestError("caf_franchise_scope_mismatch")
        seen.add(row["id"])
    active = {row["id"] for row in rows if row.get("is_active") is True}
    if not mapped <= active:
        raise ConnectionTestError("caf_franchise_scope_mismatch")
    return fingerprint(connection)
