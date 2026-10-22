# Reciprocal keys and production STAGED settings

Implemented on Radius `staging`; owner acceptance, production deployment and real
activation remain separate. CAF owns its corresponding settings/worker. No change
to existing plan/reservation/renewal/v2 provisioning/receipt paths or envelopes.

## Owner settings

Open Company → **CAF integration settings**, or
`/companies/{numeric_company_id}/integrations/caf/`. An active explicit OWNER
membership is required even for platform superusers; operators/viewers cannot
read or write connection settings. All mutations require session authentication
and CSRF. Responses are private/no-store.

1. Save agreed source, exact existing CAF company ID and administrator-allowed
   CAF HTTPS origin. The company/source binding is immutable. A CAF read key may
   initially be blank to allow the reciprocal bootstrap.
2. Map existing CAF franchise IDs; Radius allocates network mapping numbers, not
   a competing onboarding record. Disabling preserves issued identities. Changing
   mappings disables staged writes and invalidates the prior connection test.
3. Generate a Radius-issued key with explicit grants and 1–90 day validity. CAF
   needs `plans_read`, `reservations_write`, `provisionings_write`, `receipts_read`.
   The raw key is shown only in that HTTP response. Database stores its digest;
   copy it to CAF's backend settings. A subsequent GET cannot retrieve it.
4. Generate a separate scoped inbound read key in CAF and save it here. This
   outbound key is authenticated-encrypted using a separate retained Fernet key
   ring; no plaintext key/ciphertext is rendered by settings GET. Blank preserves;
   explicit removal clears. Replacing key/origin disables staged writes until
   retested. Origin changes require replacement/removal, preventing forwarding
   the previous credential to another host.
5. Test CAF connection. Radius GETs the scoped paginated company/franchise APIs
   over verified HTTPS without redirects or environment proxies, and checks exact
   active IDs and company scope. It never fetches customer documents or starts
   provisioning. Tests do not enable delivery. A changed config during the test
   cannot acquire a valid test stamp.
6. Explicitly **Enable STAGED only** after a successful test within 30 minutes.
   Both global production-STAGED and provisioning gates must be on, credential
   and fingerprint keys available, and mapping fingerprint unchanged. CAF must
   separately enable its worker/delivery. Key entry alone starts nothing.
7. Select/publish existing Radius plans with exact positive validity seconds.
   A changed plan becomes unavailable until explicitly republished/versioned.
   No price or calendar-month duration is invented.

Key rotation: issue replacement → update CAF → test → revoke old key. Revocation
immediately denies that key on all operations. CAF read-key replacement is separate.
Per-company disable blocks new reservations/renewals/provisioning but preserves
existing services and authenticated receipt GET (global provisioning API must
remain on for reconciliation). It does not activate/suspend unrelated subscribers.

## Reciprocal bootstrap API

Additive `GET /api/integrations/ecaf/v1/connection-status`, Bearer Radius-issued
key with `plans_read`; catalog server gate and HTTPS required. No browser token.
Available before per-company staged enable, so both sides can exchange keys
without a circular dependency. Current response fields:

```json
{
  "schema_version": "1.0",
  "source": "caf-portal",
  "company_ref": {"id": "exact-caf-company-id"},
  "radius_company_id": "12345",
  "franchise_refs": [{"id": "exact-caf-franchise-id"}],
  "mode": "staged",
  "staged_enabled": false,
  "grants": {
    "plans_read": true, "reservations_write": true,
    "provisionings_write": true, "receipts_read": true
  },
  "token_expires_at": "2026-11-01T00:00:00+00:00"
}
```

CAF scoped read key must likewise permit the unchanged
`GET /api/integrations/radius/v1/companies` and
`GET /api/integrations/radius/v1/companies/{id}/franchises` **before outbound CAF
delivery enable**. Exact customer/application/approval reads remain available via
CAF's same v1 contract, but Radius does not claim an activation/withdrawal consumer.

## Server rollout foundations

`CAF_CATALOG_ENABLED`, `CAF_PROVISIONING_ENABLED` and independent
`CAF_PRODUCTION_STAGED_ENABLED` all default false. A global gate alone does not
enable a company; settings test/enable is also required for writes. Catalog is a
separate read gate. `CAF_DEMO_LOCAL_HTTP` stays false in normal settings; synthetic
activation cannot be enabled through a production environment variable.

Prepare private key files with the maintained helper (never overwrites existing
keys; protect the parent directory ACL on Windows):

```sh
python scripts/prepare_caf_secrets.py --directory secrets
```

The files are `caf_fingerprint_keys.json` (key ID→hex HMAC secret) and
`caf_credential_keys.json` (key ID→Fernet key). Keep encryption keys and historical
fingerprint versions with protected backups. Do not replace/delete old versions
while ciphertext or replay records still need them. Fernet uses the established
cryptography library rather than custom encryption.

Optional `compose.caf-staged.yml` overlays protected read-only Docker secrets onto
web. Base Compose forwards the new gates, origins, key IDs and optional CA path;
normal deploys without the overlay still run with integrations off. Apply reviewed
pending migrations through0011 with the migration role before starting this code.
0010's MariaDB trigger DDL is non-atomic; back up/verify restore first.0011 adds only
the reciprocal connection table; no historical diagnostics become deliveries.

Set exact `CAF_API_ALLOWED_ORIGINS`, `CAF_FORM_URL`, `CAF_FORM_ALLOWED_ORIGINS` and
actual trusted proxy peer IPs in `CAF_CATALOG_PROXY_IPS`. The proxy must overwrite
forwarded protocol headers; web remains loopback/private. A middleware recognizes
HTTPS only from those peers, including correct HTTPS return links. Do not trust
arbitrary forwarded headers or disable TLS verification. Optional `CAF_API_CA_FILE`
is for a specifically managed CA; public production TLS normally uses system CA.

Read-only preflight inside the configured app:

```sh
python manage.py check_caf_staged
python manage.py check_caf_staged --company-id 12345 --require-enabled
```

The existing web service has restart/health supervision. Radius stages transactions
synchronously and persists receipts: there is no new Radius transport worker.
CAF must supply a supervised outbox worker, expiry/purge, bounded retries, health
and reconciliation. This is not a retention scheduler or full activation system.

Rollback: disable company's staged writes and stop CAF delivery, preserve receipts,
accepted hashes/expiry and all keys; reconcile unknown outcomes before retrying.
Do not restore stale state, delete identity tombstones or reset accepted credentials.

## Independent test HTTPS pair and owner checkpoint

The accepted HTTP demo18110/18120 is separate. New fixture ports:

- Radius `https://127.0.0.1:18220` → loopback18150, independent SQLite DB.
- CAF `https://127.0.0.1:18210` → CAF-owned loopback18160/independent PostgreSQL.
- CA `.tools/production-staged/tls/ca.crt` (public certificate); private keys and
  logins remain ignored. No system trust store is modified by the helper.

```powershell
.venv/Scripts/python.exe scripts/prepare_caf_secrets.py --directory .tools/production-staged/secrets
.venv/Scripts/python.exe scripts/local_pair_https.py --prepare-only
.venv/Scripts/python.exe scripts/run_staged_test.py
# separate hidden background processes / terminals:
.venv/Scripts/python.exe scripts/local_pair_https.py --port 18220 --upstream-port 18150
.venv/Scripts/python.exe scripts/local_pair_https.py --port 18210 --upstream-port 18160
```

Keys are prepared once. Radius private owner login is in
`.tools/production-staged/access.txt`. CAF sets `NODE_EXTRA_CA_CERTS` to the CA file
before launching Node; Radius fixture already configures its CA file. Both retain
certificate/hostname verification. A browser requires explicit trust of this test
CA in an isolated test profile; never silently install a root into the owner's OS.
TLS helper accepts only these loopback pairs and is not a deployable reverse proxy.
Normal runtime gates are exercised; the SQLite laptop fixture is not MariaDB proof.

Owner test after joint validation: exchange two keys through settings, verify saved
keys stay hidden, test mismatched franchise fails, enable separately in each app,
use same existing form/reservation/approval, then expect accepted credentials and
SUSPENDED subscriber with same Customer ID. Disable Radius writes and confirm new
delivery stops while known receipts remain readable. Revoke a test key and confirm
access denial. Test source/CI success does not imply deployment or owner acceptance.

At initial implementation checkpoint: SQLite settings/protocol tests pass; strict
verified HTTPS Radius login200. Joint new-mode exchange, MariaDB CI and owner
acceptance are still pending. Do not claim the accepted HTTP demo proves them.
