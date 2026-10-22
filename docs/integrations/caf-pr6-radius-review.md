# Radius review of CAF PR 6

Reviewed CAF proposal `b21c55daae8ccfb249aac3ebc1e190029c6aa795`:
https://github.com/vsmann3/caf-portal/pull/6

Status: Radius technical review and proposals for CAF agreement. This does not
freeze new schemas, implement endpoints or resolve the owner's pending-KYC policy.

## Accepted direction

- Company/franchise page shapes and operation names `companies:read`,
  `franchises:read`, `customers:read`, `changes:read` are suitable. Keep explicit
  source/company/franchise authorization, keyset pagination and 1–100 page limits.
- Separate current review state from immutable approved data. No pending identity
  values, document data or credentials in these reads.
- Preserve a lifetime customer master and distinct application/service request IDs.
- Approval/snapshot/version/outbox must commit atomically. Use commit-safe ordered
  publication; an ordinary sequence allocated before commit is insufficient.
- CAF can proceed with its fake-success, secret-redaction and minimal-payload fixes
  without waiting for the remaining integration response schemas.

## Customer response changes requested before freezing

Do not make a customer's singular `review` describe whichever connection was most
recently edited. Proposed replacement: nullable `identity_review` for the active
customer-profile revision, nullable `approved_profile` with its explicit approved
reference, and a separately paginated application/service-request resource.
Each connection approval must retain its exact application ID, revision and stable
service request UUID. Do not embed an unbounded list of applications in a lookup.
The existing `customer.approved` event remains unchanged pending a joint schema PR;
the new customer-master profile shape needs an explicit schema, not an inferred
rewrite of that connection-specific approval event.

Radius accepts minimal unapproved lookup state for an authorized caller:
`customer_version: 0`, null approved profile, no pending profile values. This is
informational only and cannot activate a service. Unknown/out-of-scope customer
returns scoped 404. Draft identity needs its own draft reference or null application
ID; never label a draft ID as a submitted application ID.

Runtime validation must check nested customer IDs, organization bindings and
approved version <= enclosing customer version. Draft 2020-12 structural validation
alone does not enforce equality/order between those values. Add negative fixtures
for mismatched customer/company/franchise and a future approved version.

### Ordering across multiple connections

A global customer version orders customer-profile changes. It must not cause the
first delivery of connection A's valid approval to be dropped just because a newer
connection B approval arrived first. Track profile version and per-application /
service-request approval state separately. Nor may a delayed initial provisioning
request restore withdrawn approval. Before freezing lifecycle schemas, agree an
authoritative, scoped exact-application approval read (or equivalent reconciliation
record), revision/version preconditions and per-service withdrawal ordering.
Missing or ambiguous approval evidence blocks new activation and requires
reconciliation; it must not be treated as permission to activate. This does not
decide existing-service behavior during a pending KYC revision.

## Radius-owned interface proposals for CAF review

### Plans

Return a paginated scoped catalog with plan UUID, name, positive integer version,
active flag, download/upload rates in explicit kbps, and validity. First proposal:
`validity: {duration_seconds: <positive integer>, starts_at: "activation"}`.
Calculate expiry from the first successful activation transaction in UTC; retry
never moves that anchor. Calendar-month plans need a separate agreed calendar/time
zone contract; do not silently convert them into 30 days. Do not invent configured
validity for existing rate-only plans.

If price is included, use currency ISO code and integer minor units with an explicit
minor-unit exponent, not a floating-point amount. Price display does not introduce
a payment prerequisite. Reserve a plan version in the username reservation so the
current provisioning schema need not change merely to pin a selected plan. Changed
or inactive plans block activation with an actionable conflict until reselected /
revalidated; never silently switch the customer to a different plan.

### Username reservations

Bind each reservation to authenticated source, mapped company/franchise, customer
ID, stable service request UUID, username, selected plan UUID/version and expiry.
The username must satisfy Radius's actual authentication namespace uniqueness.
POST matching live requests returns the existing reservation. Explicit renewal by
reservation ID uses the same binding; request a new idempotency key for that renewal
operation. Expired names can be reclaimed only by an atomic availability check;
never steal a name, change it silently or change the service request UUID.

Return server UTC `expires_at`, reservation UUID and the bound plan version. Define
409 codes `username_unavailable`, `reservation_expired`, `reservation_binding_conflict`
and `plan_changed`; permanent validation failures are not endless retry conditions.
An expired reservation can be replaced with a new reservation UUID for the SAME
service request before first successful credential acceptance. If the provisioning
body changes, use a new event/key through an agreed replacement approval envelope;
never mutate an already accepted idempotent request. The exact replacement envelope
is still to be agreed, rather than bypassing the existing replay-conflict rule.

### Provisioning receipt and credentials

Add operation-specific receipt lookup to avoid ambiguity when profile and
provisioning share one event ID: proposed
`GET /api/integrations/ecaf/v1/provisionings/{event_id}`. Generic event receipts
remain at the existing event path. Return source-scoped event ID, customer ID,
service request UUID, receipt status, service UUID/status when available, structured
safe error and `credential_accepted` boolean. The provisioning POST returns that
same durable receipt/status URL.

`credential_accepted: true` means the credential hash, receipt and durable reference
to the service request committed together. It is monotonic, survives later setup
failure and is visible on a matching retry and receipt lookup after a lost response.
It does not mean internet active. CAF purges its recoverable pending credential on
this exact signal, including if service setup later fails. Radius retries technical
work using the retained hash; it must never request or reset the original password.
Before acceptance, CAF's encrypted retry retention is bounded; after expiry require
explicit credential recovery, not endless storage or automatic password changes.

### Feed, lifecycle and next contract work

Use `{items,next_cursor,has_more}` and a stable resume cursor even on empty feed
pages. Bind cursors to source/operation/grants and filters. Proposal: expired cursor
returns 410 `cursor_expired` with a scoped bootstrap recovery path. Do not use a
timestamp scan as recovery. A complete bootstrap must capture a consistent scoped
snapshot plus continuation cursor, then replay committed changes after that point;
its resource/schema remains to be defined before a live consumer is enabled.

Withdrawal/reapproval must identify the precise approval/application/service request
being affected and carry ordered versions; customer identity review is a separate
concept. Unknown lifecycle types must block/reconcile rather than be silently skipped.
Organization/staff lifecycle, KYC field policy/revision decisions, projections and
safe form-entry shapes remain joint follow-up schemas, not accepted endpoints.

## Validation and requested CAF response

Radius reran the exact nine CAF offline contract tests from `b21c55d` in an isolated
ignored copy: all passed. No CAF working-tree edits, runtime calls or production
changes were made. Existing reference approval/provisioning schemas were unchanged.

Please respond with agreement or concrete alternatives for customer-master versus
connection approval reads, per-service ordering, pinned plan/reservation behavior,
operation-specific durable receipts and commit-safe bootstrap/feed recovery. Then
publish linked schema/fixture changes before implementing incompatible consumers.
