"""Exercise owner settings over real, verified localhost HTTPS; synthetic fixture only.

Bootstraps a private Radius key file for CAF, without enabling delivery. Supply a
CAF read-key file to additionally test scopes and explicitly enable this fixture.
"""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caf-company-id", required=True)
    parser.add_argument("--caf-franchise-id", required=True)
    parser.add_argument("--caf-read-key-file", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent / ".tools" / "production-staged"
    private = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    db = sqlite3.connect((root / "radius-staged.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    row = db.execute("SELECT company_id,id FROM core_tenant WHERE slug='caf-staged-test'").fetchone()
    if not row:
        raise SystemExit("Expected isolated HTTPS test tenant is missing")
    company, tenant = row
    base = "https://127.0.0.1:18220"
    url = f"/companies/{company}/integrations/caf/"
    cookies = http.cookiejar.CookieJar()
    context = ssl.create_default_context(cafile=str(root / "tls" / "ca.crt"))
    client = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(cookies))

    def request(path, form=None, token=None):
        headers = {"Origin": base, "Referer": base + path}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None
        if form is not None:
            csrf = next(cookie.value for cookie in cookies if cookie.name == "radius_staged_test_csrf")
            data = urllib.parse.urlencode({**form, "csrfmiddlewaretoken": csrf}).encode()
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            response = client.open(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP{response.status} at test path {path}")
        return body, response.headers

    request("/accounts/login/")
    request("/accounts/login/", {"username": "staged-admin", "password": private["admin_password"]})
    page, _ = request(url)
    if "CAF integration" not in page:
        raise RuntimeError("Owner login did not reach settings")
    saved = {"action": "save", "source": "caf-portal", "caf_company_id": args.caf_company_id,
             "origin": "https://127.0.0.1:18210"}
    if args.caf_read_key_file:
        saved["caf_read_key"] = args.caf_read_key_file.read_text(encoding="utf-8-sig").strip()
    body, _ = request(url, saved)
    if "Connection saved" not in body:
        raise RuntimeError("Connection save did not succeed; inspect settings (no secret printed)")
    mapped = db.execute("SELECT f.id FROM core_caffranchisebinding f JOIN core_cafcompanybinding b ON b.id=f.company_id WHERE b.tenant_id=? AND f.caf_franchise_id=?", (tenant, args.caf_franchise_id)).fetchone()
    if not mapped:
        body, _ = request(url, {"action": "map_franchise", "caf_franchise_id": args.caf_franchise_id, "name": "HTTPS test CAF franchise"})
        if "Franchise mapped" not in body:
            raise RuntimeError("Franchise mapping failed")
    keyfile = root / "radius-connection.json"
    if keyfile.exists():
        config = json.loads(keyfile.read_text(encoding="utf-8"))
        if config["caf_company_id"] != args.caf_company_id or config["caf_franchise_id"] != args.caf_franchise_id:
            raise RuntimeError("Existing private fixture connection conflicts; no key overwritten")
    else:
        body, headers = request(url, {"action": "issue", "expires_days": "7", "plans_read": "on", "reservations_write": "on", "provisionings_write": "on", "receipts_read": "on"})
        match = re.search(r'id="issued-radius-key">(nlcaf_[0-9a-f]{32}\.[A-Za-z0-9_-]{43})</code>', body)
        if not match or "no-store" not in headers.get("Cache-Control", ""):
            raise RuntimeError("One-time key issuance failed")
        config = {"radius_base_url": base, "source_id": "caf-portal", "caf_company_id": args.caf_company_id,
                  "caf_franchise_id": args.caf_franchise_id, "radius_company_id": str(company), "token": match[1],
                  "token_id": str(uuid.UUID(hex=match[1][6:38]))}
        descriptor = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(config, stream)
    page, headers = request(url)
    if config["token"] in page or (args.caf_read_key_file and saved["caf_read_key"] in page):
        raise RuntimeError("Secret unexpectedly rendered on settings GET")
    plan = db.execute("SELECT id FROM core_plan WHERE tenant_id=? ORDER BY id LIMIT 1", (tenant,)).fetchone()[0]
    body, _ = request(url, {"action": "publish", "plan_id": str(uuid.UUID(plan)), "duration_seconds": "604800"})
    if "Plan publication updated" not in body:
        raise RuntimeError("Owner publication failed")
    status, _ = request("/api/integrations/ecaf/v1/connection-status", token=config["token"])
    status = json.loads(status)
    if status["company_ref"]["id"] != args.caf_company_id or not all(status["grants"].values()):
        raise RuntimeError("Scoped status or grants mismatch")
    if args.caf_read_key_file:
        body, _ = request(url, {"action": "test"})
        if "scopes verified" not in body:
            raise RuntimeError("Real scoped CAF connection test failed; inspect safe test_result in settings")
        body, _ = request(url, {"action": "enable"})
        if "Staged provisioning enabled" not in body:
            raise RuntimeError("Explicit isolated STAGED enable failed")
    safe = {"radius_url": base, "settings_http": "PASS", "verified_tls": True,
            "company_id": str(company), "caf_company_id": args.caf_company_id,
            "caf_franchise_id": args.caf_franchise_id, "key_hidden_on_get": True,
            "real_caf_scope_test": bool(args.caf_read_key_file), "network_activation": False}
    (root / "settings-http-result.json").write_text(json.dumps(safe, indent=2), encoding="utf-8")
    print("PASS real HTTPS owner settings, mapping, one-time grants, hidden GET and published plan.")
    print("CAF scopes tested and isolated STAGED enabled." if args.caf_read_key_file else "Private key file prepared for CAF; STAGED remains disabled.")


if __name__ == "__main__":
    main()
