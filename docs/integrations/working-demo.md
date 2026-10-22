# CAF and Radius working-model increment

This increment implements actual Radius endpoints and a separately runnable local
demo. The counterpart is the existing CAF form extended by the CAF developer.
No production deployment or live NAS activation is part of this increment.

## Radius runtime

- Existing authenticated company-scoped plan catalog and explicit plan publication.
- POST `/api/integrations/ecaf/v1/username-reservations` with strict JSON fields:
  customer_id, service_request_id, username, plan_id, plan_version, company_ref,
  franchise_ref. UUID Idempotency-Key; returns 201 with the agreed reservation.
- POST `/api/integrations/ecaf/v1/username-reservations/{UUID}/renew`, body `{}`,
  fresh operation-scoped UUID key; returns 200. Same key cannot target another ID.
- POST `/api/integrations/ecaf/v2/provisionings` with the agreed v2 envelope:
  schema_version 2.0, provisioning_request_id, supersedes_request_id, unchanged
  approval event and service fields. Key is the immutable delivery UUID.
- GET `/api/integrations/ecaf/v2/provisionings/{delivery UUID}` returns the scoped
  durable receipt. Acceptance is not inferred from a generic 202.
- Staff directory displays and filters the permanent CAF 10-digit customer ID.
  Multiple connections retain one customer link; local UUIDs remain service IDs.
- Configured Add Customer opens CAF's actual form using safe company prefill and
  return URL. CAF must enforce its own actor scopes and return allowlist.

New service token grants are reservations_write, provisionings_write, receipts_read;
all default false. `CAF_PROVISIONING_ENABLED` defaults false. Separate fingerprint
key ring configured by `CAF_FINGERPRINT_KEYS_FILE` and active key ID. Each ring value
is 32+ secret bytes encoded as hex. Password-bearing request replay and immutable
binding fingerprints use separately domain-bound keyed RFC8785 HMACs. No plaintext
request or initial password is stored in receipts, logs or customer projections.

Tenant row locks serialize claims and service acceptance in each company. Durable
unique source/service and source/operation/delivery identities prevent duplicates.
An expired-reservation v2 predecessor may be replaced only with an unchanged
approval/service/password/plan version and no prior acceptance/successor. Retained
key versions must remain available for verification. Initial provisioning always
creates a suspended subscriber in normal settings: exact live CAF authorization
and withdrawal handling are not bypassed by receiving an approval envelope.

New tables/fields are migration0010; existing immutable token guards are restored
after SQLite table rebuilds. PostgreSQL is CAF-owned; Radius does not access it.
The schema validator and canonicalizer reuse jsonschema and rfc8785 packages.

Not implemented by this slice: production activation authorization/revocation
consumer, staff/organization onboarding feeds, operational projections, IP/hotspot,
billing/wallet accounting, and a production reconciliation/retention scheduler.
Do not present the demo as completion of those wider product features.

## Independent laptop environment

Run with the project virtual environment:

```powershell
.venv/Scripts/python.exe scripts/prepare_demo_postgres.py
.venv/Scripts/python.exe scripts/run_caf_demo.py
```

The first command is an optional Windows helper for CAF's independent PostgreSQL16
database. It downloads the official EDB portable archive into ignored `.tools`,
checks its pinned SHA256, extracts server files, and starts a cluster ONLY on
127.0.0.1:18130. It installs no Windows service. The dedicated `caf_demo_netloom`
database/app role and private `.tools/integration-demo/caf-database.json` let the
CAF developer run migrations/seed and its Node app locally. No database reset,
production connection, automatic CAF merge or application deployment is performed.
Use CAF's own working-model launch instructions for its app on18110.

This creates `.tools/integration-demo/` (ignored): a NEW SQLite database, separate
signing/fingerprint keys, synthetic company/franchise/plans, private connection
metadata and demo login details. It does not read production databases or secrets.
The server binds only `127.0.0.1:18120`. CAF's isolated existing-form app uses
`127.0.0.1:18110`. Default external IDs are `netloom-demo-company` and
`netloom-demo-franchise`; use CLI overrides only when CAF's seed agrees.

Radius login details: `.tools/integration-demo/access.txt`.
CAF backend token/plan IDs: `.tools/integration-demo/connection.json`; never paste
or commit that file. Parent Windows ACL protection applies to demo credential files.
Re-running preparation preserves the database and login; no reset/deletion is done.

By default service provisioning is STAGED/SUSPENDED pending authorization.
`--synthetic-activation` explicitly enables a local-only teaching shortcut, allowed
only in demo settings with SQLite and no enabled NAS. CAF must also explicitly
accept/label synthetic active receipts in its own isolated demo. This does not
validate distributed withdrawal fencing or authorize real internet access. Real
settings never enable it through an environment variable. No UDP ports are opened.

## Verified working pair and owner test

Both local apps are running: CAF http://127.0.0.1:18110 and Radius
http://127.0.0.1:18120. Production domains were not updated. Two actual HTTP
journeys passed, including an additional connection reusing Customer ID
`1000000000`. Tests exercised real plan fetching, reservations, CAF submission,
franchise approval denial, company approval, automatic worker delivery, durable
credential acceptance, and a retry without duplicate service/password/expiry reset.
Both connections remain STAGED/SUSPENDED; internet activation is disabled.

Reproduce with synthetic data only (creates another test application):

```powershell
.venv/Scripts/python.exe scripts/test_joint_caf_demo.py --caf-demo-dir E:/OpenCode/caf-portal/.tools/working-demo
# Optional additional connection: append --existing-customer-id 1000000000
```

Safe results are in ignored `.tools/integration-demo/joint-http-result.json`.
CAF also reported real Chrome journey/PDF/return-link verification. Owner Vikas
tested and accepted this isolated STAGED milestone and authorized GitHub main,
as recorded in the CAF coordination handoff. CAF implementation is b9ad5b0,
merged via PR8 after PR6/7; exact CAF main is
`d2a71e077d419a43f244fe7e068b5537710c41ab` (independently checked remotely).
Radius implementation/evidence already reside on main through778b3b7. This is
acceptance of the local staged model only; production enablement and real network
activation remain separate decisions. The following checklist is retained for
reproduction and future regression testing.

1. Open Radius using `.tools/integration-demo/access.txt`. Open company10002,
   Users, and search `1000000000`: expect two suspended connections with one ID.
2. Click **Add customer using CAF form**. CAF opens in a new tab. CAF private
   logins are in `E:/OpenCode/caf-portal/.tools/working-demo/access.txt`.
   Use `demo-counter@caf.example.test` to submit synthetic customer/KYC data.
3. Select the demo company/franchise and a **Published RADIUS plan**. Enter a
   unique **Reserved service username**, then **Save draft and reserve RADIUS
   username**. Complete and submit the CAF. No new Radius service exists yet.
4. Sign into CAF as `demo-company@caf.example.test` and approve the application.
   Allow the automatic worker a few seconds. Expect **STAGED**, accepted
   credentials, and the same 10-digit ID/username/plan in Radius, **SUSPENDED**.
5. Refresh both apps and search the ID in Radius. Optionally create another CAF
   using **Existing approved Customer ID (optional)** and a different username:
   expect another connection under the same ID.
6. Report actual results to the developers before this milestone is owner accepted.

Use only synthetic proof images/details. This model verifies approved onboarding
and staged provisioning; production activation, wallets/billing and the remaining
product scope above are separate milestones.
