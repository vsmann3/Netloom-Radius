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
.venv/Scripts/python.exe scripts/run_caf_demo.py
```

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

## Owner test after the two local apps pass joint verification

1. Log into the local Radius URL using the private access file.
2. Open the demo company, Users, and Add Customer using CAF form. Expect the same
   CAF application in a new tab. Use only synthetic customer/KYC data.
3. Select the mapped company/franchise. Expect the two real Radius demo plans.
4. Complete the CAF draft and reserve a username. Saving/submitting must not create
   an active Radius service. Record the CAF-issued 10-digit Customer ID.
5. Approve through CAF and process its delivery. Expect a durable accepted receipt
   and the SAME ID/username/plan in Radius. Default stage-only mode remains suspended;
   coordinated synthetic-active mode clearly labels its isolated behavior.
6. Retry delivery and refresh both apps. Expect one connection, unchanged expiry,
   no credential reset. Search the customer ID in Radius and confirm the result.
7. Report results before this milestone is marked owner accepted.

These are intended joint acceptance steps. The final handoff must state which
apps are actually running and the jointly verified outcome, not infer readiness
from standalone fixture tests or assume production URLs were updated.
