# CAF plan catalog: first runtime slice

Implemented in source, not deployed or live-accepted with CAF. This slice provides
only company-scoped plan reads. Username reservations, customer/service import,
credentials, approval/authorization processing and activation are not implemented.
No customer ID is allocated here. Franchise-scoped credentials are not supported
yet; do not give a franchise actor a company-wide catalog service token.

## Request and response

`GET /api/integrations/ecaf/v1/companies/{radius_company_id}/plans?limit=100&cursor=...`

Backend-only `Authorization: Bearer <service token>`. Company IDs are public numeric
strings (5+ digits), not tenant UUIDs or CAF company CUIDs. The reviewed CAF CUID
maps explicitly through `CAFCompanyBinding`; no name matching or default company.
One token grants one source/company binding and the explicit `plans:read` operation.
Browser sessions/staff cookies do not authenticate this endpoint.

Returns the accepted `planPage` shape: items, next_cursor and has_more. Each plan
has UUID, numeric-string radius_company_id, name, positive version, active=true,
upload/download kbps and positive duration_seconds starting at activation. Optional
price is omitted: this means price is unavailable, NOT that the plan is free.
There is no invented calendar-month conversion or expiry for legacy plans.

Only active explicitly published plan snapshots appear. If underlying name/rates
change, the plan disappears until republished, preventing an old version from
advertising changed settings. Republishing increments the version; identical
publication is idempotent. Withdrawal increments version and hides the plan.
Versioned reservations will also need to validate publication/current plan before
future provisioning; this endpoint alone makes no provisioning guarantee.

Peer review fd374b4 identified case/trailing-space equality as a publication risk.
The earlier 1feb9ee binary collation fixed case sensitivity but did not establish
trailing-space significance on PAD SPACE collations. Publication names now compare
complete binary strings using CAST AS BINARY on MariaDB and CAST AS BLOB on SQLite,
before keyset filtering/LIMIT. No Python post-pagination filtering is used. See
[MariaDB binary comparison semantics](https://mariadb.com/docs/server/reference/sql-functions/string-functions/binary-operator).
The regression exercises stale rows before/between/after valid rows, exact page
boundaries, case-only/one-space/two-space changes and republish version increments.
MariaDB CI prints the actual column collation with its regression PASS marker.

Pages use plan UUID keyset order, 1–100 rows (default 100). Signed cursors expire
after 15 minutes and bind company, binding and token ID. Rotation requires starting
a fresh listing. Directory paging is not a consistent snapshot or a change feed.
Unknown/repeated query fields and malformed bounds/cursors return structured 400.

All responses are no-store JSON. Errors include error code/message/retryable and
UUID request_id. Invalid/expired/revoked token or inactive company/binding: 401;
missing operation grant: 403; wrong company: scoped 404; unsupported method: 405;
per-token 60-request UTC-minute quota: 429 with Retry-After; database outage: safe
503. Quota updates serialize on the token row. Unauthenticated traffic limits
still belong at the edge before a public pilot.

## Setup for a later integration environment

Migrations 0007–0009 create separate integration tables and protect identity
bindings with database triggers on MariaDB and SQLite. They do not alter the AAA
authorization view or subscribers. Normal token revocation and overlapping token
rotation are supported; moving an issued token to another binding or rewriting
its secret digest is rejected. Binding identity/source/tenant are immutable.

The catalog defaults disabled. Enable `CAF_CATALOG_ENABLED=true` only after
configuration. HTTPS is mandatory. Behind nginx, keep the app port private and
configure `CAF_CATALOG_PROXY_IPS` to the exact backend peer IP nginx uses as seen by
Django. nginx must overwrite X-Forwarded-Proto (the existing template does). Empty
trusts no proxy headers; arbitrary public forwarding headers never prove HTTPS.
This setting is for the catalog endpoint only, not a global forwarded-header trust.

An existing active company owner may bind an existing CAF company and issue a
30-day token (configurable 1–90 days) into a NEW protected file:

```sh
python manage.py configure_caf_catalog --actor suradmin --company-id 10001 \
  --source caf-portal --caf-company-id '<exact CAF company CUID>' \
  --token-file /protected/path/caf-catalog-token
```

Use the real public company number, not this example. The parent directory must
already exist and be protected. POSIX creation uses 0600; on Windows protect the
parent ACL separately. The command never prints the secret and never overwrites
an existing path. Only a digest is stored; setup and its audit commit together.
If file creation/audit fails, the transaction rolls back and a newly created file
is removed. A process crash can leave an orphan file: reconcile token ID before
using it; a file's existence is not proof its database transaction committed.
Deliver the secret to CAF outside Git/messages. For rotation issue a new file/token,
switch the sender, then revoke the old token (`active=False`) through controlled
administration. No secret appears in a read API.

An owner/operator with explicit company membership publishes an existing plan:

```sh
python manage.py publish_caf_plan --actor suradmin --plan-id '<plan UUID>' \
  --duration-seconds 2592000
```

This example is exactly 30 elapsed days, not a calendar month. Choose the actual
business validity. Add `--withdraw` to unpublish. The command audits publication;
it does not change any subscriber's plan or expiry or create a customer.

## Contract review and validation

CAF source 36a574765bf4598e771f15e0daad3b5392d8918f: all 38 offline reference tests
reran successfully. Draft Radius PR 1 remains a proposal bundle, unmerged. Its
logical authorization model is technically aligned; unknown later withdrawals and
pending-KYC continuation still need owner policy before unattended activation.
The proposed 24-hour absolute CAF credential-ciphertext window is acceptable as a
technical delivery bound, provided expired/unknown acceptance requires reconciliation
and explicit recovery. It never extends because of retries or resets passwords.

Application tests cover isolation, scope, secret hashing/file rollback, rotation,
expiry/revocation, HTTPS peer trust, publication version/validity, signed pagination,
quotas, database outage and direct-write binding immutability. SQLite does not prove
MariaDB locking or trigger syntax: the normal Linux SQL/PAP CI suite is required
before treating this source increment as verified for MariaDB. No deployment,
live CAF acceptance, reservation or activation is claimed by these tests.
