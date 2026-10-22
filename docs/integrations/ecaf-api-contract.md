# CAF Portal ↔ Netloom Radius API integration proposal

Status: proposed contract for both developers; endpoints below are NOT implemented
or enabled by this document. No CAF repository changes were made here.

Reviewed CAF main commit: `05dbe819ff52a5fb022965a1113bd94981b2f167`.
Repository: https://github.com/vsmann3/caf-portal
CAF developer should check for changes since this commit before implementation.

## 1. Ownership

| CAF Portal owns | Netloom Radius owns |
| --- | --- |
| Customer ID issuance and customer/CAF identity | Local service/subscriber UUID and network account state |
| Applicant/contact/installation details | PPPoE username, credential provisioning and password hashes |
| Identity documents, photos, signatures, signed CAF/PDF | Plans, rate attributes, expiry, suspension and Disconnect |
| Review, approval, rejection, approved snapshots | NAS registrations/secrets, authentication and accounting |
| Company/franchise onboarding metadata and external references | Operational roles, franchise wallet/renewal/commission rules already in scope |

Do not build a second eCAF form or duplicate document storage in Radius. The Radius
UI should offer “Open eCAF” and display a minimal customer summary imported by API.
Each application retains its own database and login. API integration does not grant
cross-application staff access; shared sign-in, if wanted, is a separate OIDC project.

## 2. Findings from the existing CAF source

- Prisma has `CustomerNumber`, `CafDraft.customerId` and
  `CustomerApplication.customerId`. Migration `20261022090000_customer_ids` uses a
  PostgreSQL sequence from 1000000000 through 9999999999, NO CYCLE, with a digit
  constraint. IDs are strings and survive draft submission/corrections.
- CustomerApplication has company/franchise references, broadbandUsername,
  revision, approvedSnapshot, review status and a RadiusSync relation.
- `src/lib/radius/types.ts` already defines an adapter, but its subscriber payload
  omits customerId, application ID and revision. It includes identity-proof data
  that Radius does not need.
- `src/lib/radius/index.ts` always returns NoopRadiusAdapter. The no-op returns
  `ok: true, remoteId: "SKIPPED"`; this must never mean provisioned/success.
- Approval updates the CAF, then creates RadiusSync and invokes the adapter inline.
  The reviewed flow does not atomically commit approval and its sync record. A
  durable delivery worker/reconciliation loop is not demonstrated by this code.
- Existing application/document APIs use staff session cookies. Do not automate
  a staff login or reuse its browser JWT as service authentication.
- Radius configuration GET/PUT returns the config object, including apiKey if
  saved. New integration secrets must be encrypted, redacted on reads and omitted
  from audits, responsePayload and logs.

Source links at the reviewed revision:
- [Customer-ID migration](https://github.com/vsmann3/caf-portal/blob/05dbe819ff52a5fb022965a1113bd94981b2f167/prisma/migrations/20261022090000_customer_ids/migration.sql)
- [Schema](https://github.com/vsmann3/caf-portal/blob/05dbe819ff52a5fb022965a1113bd94981b2f167/prisma/schema.prisma)
- [Adapter types](https://github.com/vsmann3/caf-portal/blob/05dbe819ff52a5fb022965a1113bd94981b2f167/src/lib/radius/types.ts)
- [Adapter implementation](https://github.com/vsmann3/caf-portal/blob/05dbe819ff52a5fb022965a1113bd94981b2f167/src/lib/radius/index.ts)
- [Approval handler](https://github.com/vsmann3/caf-portal/blob/05dbe819ff52a5fb022965a1113bd94981b2f167/src/app/api/applications/%5Bid%5D/status/route.ts)

## 3. Identity and company/franchise mapping

Use CAF `customerId` as the shared business/customer identifier everywhere. Transport
it as a string matching `^[1-9][0-9]{9}$`; Radius must NEVER allocate or renumber it.
This supersedes the question about generating separate numeric subscriber IDs here.

Keep these concepts separate:

| Identifier | Authority | Purpose |
| --- | --- | --- |
| customer_id (10 digits) | CAF | Customer identity, display and search in both systems |
| caf.application_id / caf.number / caf.revision | CAF | Particular application and approved revision |
| company_ref.id / franchise_ref.id | CAF | External CUID references |
| Radius company_id (5+ digits) / tenant UUID | Radius | Public company navigation / internal ownership |
| subscriber/service UUID | Radius | Individual network connection; not a new customer number |
| PPPoE username | Radius | Authentication name; may differ from customer_id |

Maintain reviewed bindings `(integration source, CAF company CUID) → Radius tenant`
and `(source, CAF franchise CUID) → Radius franchise in that tenant`. Company codes
and names are display/diagnostic values, never authorization or automatic matching.
Franchise support/mappings must be implemented on Radius before franchise-scoped
provisioning goes live. Missing mappings must block processing, not select a default.

Use a CustomerLink unique on `(source, customer_id)` and make its company binding
immutable through routine sync. A subscriber references that link. Reject a repeated
customer ID with a different company/franchise binding; transfers require an
explicit reviewed transfer workflow. Unknown-source IDs cannot merge by name/mobile.

Design the link for one customer with multiple services even if the first rollout
allows only one. Important CAF question: customerId is currently unique per draft /
application, rather than a separate reusable Customer entity. Before supporting a
second CAF/relocation/service for the same customer, define reuse of the original
customer ID instead of allocating a new customer number. Corrections to an existing
CAF already preserve its ID; new CAFs are a separate case.

Existing Radius accounts without customer_id must be linked explicitly; never
auto-merge by username, phone or name, and never fabricate CAF IDs for them.

## 4. Normal workflow

1. Operator opens the real CAF Portal (new CAF or an existing customer link).
2. CAF owns data capture, document uploads and review.
3. Approval + immutable approved integration snapshot + outgoing event are committed
   in ONE PostgreSQL transaction. Even if delivery is disabled, retain the event.
4. A CAF background worker delivers the event below to Radius with a service token.
5. Radius validates source scope, company/franchise bindings, event identity,
   customer ID and version, then durably stores its inbox receipt and returns 202.
6. Radius processes the inbox into a CustomerLink/profile projection. This can be
   `applied` while the network service remains `pending_service_setup`.
7. Radius creates/enables network service only after a valid local plan, username,
   credentials, expiry and required commercial authorization are present. CAF
   approval alone must not invent a paid renewal or activate an incomplete account.
8. CAF polls the Radius receipt/service endpoint to show “Queued”, “Customer linked”,
   “Service setup required”, “Active”, or an actionable failure. 202 is not active.

Existing network authentication always uses local FreeRADIUS/MariaDB state. It
must not call CAF during a login packet. A CAF outage delays new onboarding/sync;
it does not interrupt existing subscriber authentication.

## 5. Proposed endpoints to implement

All paths are versioned and use HTTPS server-to-server requests.

### CAF developer implements

| Method/path under CAF host | Purpose |
| --- | --- |
| GET `/api/integrations/radius/v1/companies` | Scoped company references for mapping; cursor pagination |
| GET `/api/integrations/radius/v1/companies/{caf_company_id}/franchises` | Scoped franchise references for mapping; cursor pagination |
| GET `/api/integrations/radius/v1/customers/{customer_id}` | Minimal authoritative snapshot, approval status and customer_version |
| GET `/api/integrations/radius/v1/changes?cursor=...&limit=100` | Durable ordered change feed for reconciliation, including withdrawals |

Snapshot responses must carry current review status and an approved snapshot
reference; never return draft contact data as approved. Feed uses an opaque cursor
over a durable sequence, not just updatedAt timestamps. Return items, next_cursor
and has_more. Enforce 1–100 item page sizes. Snapshot lookup must support the
10-digit customer ID directly, rather than requiring a staff cookie/application ID.

### Radius developer implements here

| Method/path under Radius host | Purpose |
| --- | --- |
| POST `/api/integrations/ecaf/v1/events` | Persist an incoming approval event; return receipt |
| GET `/api/integrations/ecaf/v1/events/{event_id}` | Receipt and processing outcome |
| GET `/api/integrations/ecaf/v1/customers/{customer_id}/services` | Scoped network-service statuses and safe references |
| GET `/api/integrations/ecaf/v1/companies/{radius_company_id}/plans` | Plan UUID, name and upload/download rates for an optional CAF selector |

An optional username availability/reservation API can follow. CAF's current username
generator checks only its own database, so it cannot guarantee availability in
Radius. Radius must atomically reject a conflict; never overwrite another account.
Do not assume planName/bandwidth text identifies a Radius plan. If the CAF UI offers
plan selection, it must use the Radius plan UUID returned by the scoped plan API;
operational activation still follows Radius authorization and commercial rules.

Do not reuse the existing Radius staff session APIs for these endpoints.

## 6. Phase-one approval event

See `ecaf-event.schema.json` and `ecaf-event.example.json` alongside this document.
These define customer.approved only. The event is a minimal projection of the
approved snapshot, not a dump of CustomerApplication/approvedSnapshot.

Required envelope: schema_version, event_id UUID, event_type, occurred_at UTC,
customer_version, customer_id, company_ref, franchise_ref, caf and profile.name.
Optional profile.mobile/email are for operational contact display. Installation
address remains in CAF initially; add a minimum agreed service-location projection
only if Radius needs it for a concrete operational workflow.

NEVER send idNumber, idProofType, DOB, document bytes/keys, signed PDFs, portal
passwords, Radius passwords/hashes, NAS shared secrets or browser session tokens.

`customer_version` is a new monotonic integration version for this customer,
incremented on every integration-relevant change in a transaction. Existing CAF
revision alone is insufficient for ordering every future review/status event.
Store both version and approved CAF revision. Never order by delivery time.

### Request

```
POST /api/integrations/ecaf/v1/events
Authorization: Bearer <company-scoped service token>
Content-Type: application/json
Idempotency-Key: <same UUID as event_id>
```

### Initial durable receipt (HTTP 202)

```json
{
  "event_id": "17f496c8-4ff8-4fae-bf57-74b76931afef",
  "receipt_status": "accepted",
  "customer_id": "1000000123",
  "status_url": "/api/integrations/ecaf/v1/events/17f496c8-4ff8-4fae-bf57-74b76931afef"
}
```

### Later status response (HTTP 200; illustrative, not a live account)

```json
{
  "event_id": "17f496c8-4ff8-4fae-bf57-74b76931afef",
  "receipt_status": "applied",
  "customer_id": "1000000123",
  "applied_customer_version": 1,
  "service_status": "pending_service_setup",
  "services": [],
  "error": null
}
```

Receipt states: accepted, processing, applied, ignored, blocked, failed. `applied`
means the approved customer projection was applied, NOT that a PPPoE session exists.
Service summaries expose service UUID, username, plan UUID, expiry and operational
status only. No passwords, arbitrary document URLs or raw internal errors.

## 7. Authentication, scopes and delivery correctness

- Generate separate high-entropy service tokens for each direction/company/source.
  Receivers store token hashes; senders encrypt or mount the token as a secret.
  Support revocation/rotation with key IDs. No hard-coded/shared staff credentials.
- Bind tokens to explicit external company/franchise scopes, integration source
  and operations (e.g. events:write, receipts:read, customers:read, plans:read).
  A company/franchise ID in JSON or a URL never enlarges those grants.
- Persist inbox uniqueness on `(source, event_id)`, payload digest and scope, with
  a stable receipt. A matching retry returns its current receipt without repeating
  side effects; the same ID with a changed payload returns 409. Hash canonical
  validated JSON with SHA-256 over RFC 8785 JCS UTF-8 bytes; transport whitespace/key
  ordering is not a change. Reject duplicate JSON keys and non-finite numbers before
  validation. Reference: https://www.rfc-editor.org/rfc/rfc8785
- Update projection + audit + queued local service work atomically. Lock the
  customer link while applying versions. Older versions are ignored, never applied.
  Same customer/version with a different approved projection is a 409 conflict.
- Queue approval atomically in CAF; deliver outside the review HTTP request. Use
  bounded timeouts, exponential backoff/jitter, a visible failed/dead-letter state
  and operator retry. Refresh credentials on 401 rather than retry forever.
- Retry network errors, 429 (respect Retry-After) and 5xx with the SAME event/key.
  Fix mapping/validation/version conflicts before retrying 4xx. Poll by event ID
  after an ambiguous timeout to discover whether the request was committed.
- Restrict payloads to 64 KiB, validate JSON/schema, rate-limit clients, audit source,
  customer ID, company, version, outcome and actor reference without logging PII.
- Reconcile through the CAF change feed and Radius receipt/service reads. Persist
  cursor only after all events in that page are durably accepted/processed; do not
  lose a page on partial failure. Reconcile even when pushes normally work.
- Service tokens are backend-only. Do not return stored secrets from CAF settings
  GET/PUT; use masked configured flags and separate write-only secret input.
  The current global RadiusConfig needs company-scoped connection/key selection;
  do not let one franchise choose a different company's connection or destination.

Errors use `{ "error": { "code": "...", "message": "...", "retryable": false },
"request_id": "..." }`. Suggested HTTP codes: 400 malformed request/schema; 401
missing/invalid token; 403 scope denied; 404 scoped resource not found; 409 replay,
identity/username/version conflict; 422 invalid mapping/business request; 429 limit;
503 temporary dependency outage. Acknowledgement requires durable storage first.

## 8. Lifecycle rules before live acceptance

The phase-one schema accepts approvals only. Agree and implement versioned events
for approval withdrawal/review changes and reapproval before unattended live use.
Do not equate REJECTED or contact edits with service deletion. Withdrawal blocks
new activation; its effect on an existing service must follow an explicitly
configured policy and audited Radius action, not an arbitrary generic patch.

Replayed approval/profile updates must NEVER reset an existing password, clear an
operational suspension, change plan/expiry, debit a wallet or renew twice. CAF
profile state and Radius service state have different field owners. Relocations,
franchise/company transfers and account merges need explicit conflict-reviewed
operations, not implicit reassignment during profile sync.

## 9. Developer handoff

CAF developer:
1. Add customer_id and versioned minimal approved snapshot/event types to the adapter.
2. Replace the no-op success with honest disabled/unimplemented status until wired.
3. Add service authentication and the four CAF endpoints above with scope tests.
4. Commit approval/snapshot/outbox atomically; implement worker, retry, receipt polling
   and change-feed reconciliation. Do not persist broad identity payloads in RadiusSync.
5. Make integration secrets write-only/redacted and preserve customer IDs on retries.

Radius developer (this repository):
1. Implement scoped integration credentials, external company/franchise mappings,
   CustomerLink/customer_id projection and inbox processing.
2. Implement event receipt/status, customer service read and scoped plan endpoints.
3. Display/filter the CAF 10-digit ID as the main customer identifier in the users
   directory. Preserve local service UUIDs and existing usernames/relationships.
4. Replace customer onboarding entry with CAF links/approved-customer selection;
   keep network service setup in Radius. No second eCAF form/document upload flow.
5. Test both systems against the same fixtures and contract before enabling sync.

Joint acceptance: one approved CAF imports once; retries/timeouts do not duplicate;
out-of-order revisions do not roll back data; cross-company/franchise requests fail;
unknown mappings block; disabled/no-op never reports success; rejected/draft data
cannot activate; revocation/reapproval policies hold; existing suspended services
stay suspended; no passwords/docs/ID-proof data cross; outages recover through
reconciliation; main customer ID is identical on both UIs.
