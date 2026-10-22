# Radius response to CAF round two

Reviewed CAF `9a521bd876b945daa289fdd797c3b175f042bfa7`, PR 6.
Status: technical agreement on the explicitly accepted items below; activation
authorization remains a proposal, not an implemented guarantee or release approval.

## Accepted interfaces

Accept the separated customer/profile/application reads, independent per-service
approval ordering, fixed-duration activation anchor, pinned plan/reservation
bindings, dedicated provisioning receipt lookup and monotonic `receipt_version`.
Accept empty-body reservation renewal at the proposed v1 renewal path with a fresh
operation-scoped key. Source is derived from service authentication; a body or
response source ID is only a consistency check, never an authority selector.

For identity comparison, absent mobile/email and explicit null normalize to null;
present strings compare exactly after the shared validation policy. No implicit
case folding, whitespace correction or phone normalization during conflict checks.
Compare organizational IDs, not mutable organization display labels. Transport
replay HMAC still covers the entire validated request and distinguishes changed
payloads. This normalization is for profile equivalence only.

Accept opt-in v2 provisioning envelopes with independent immutable delivery IDs
and `supersedes_request_id`, preserving v1 event-ID semantics. Do not fabricate a
fresh approval merely to renew a reservation. Required replacement implementation:

- Lock one service request across v1 and v2 operations; successful acceptance in
  either namespace blocks any replacement or second credential write in the other.
- Replace only the current chain leaf with durable `reservation_expired`, false
  acceptance and no accepted successor. Prevent replacement forks and cycles;
  reject self-supersession. Unknown outcomes require receipt reconciliation.
- Compare the complete approval and immutable service fields using a separate
  server-keyed canonical HMAC that excludes only delivery/supersession IDs and
  reservation ID. Retain a separate complete-request replay HMAC. Pin and compare
  the reservation's plan version even though the v1 service body omits it.
- Same password is mandatory. Key rotation must retain the fingerprint key/version
  for the supported replacement window; no plaintext or password-guessable digest.
- An expired reservation failure must be committed before credential acceptance.
  Superseding it and accepting its successor are atomic under the same service lock.
- Retain a durable uniqueness/tombstone record after receipt archival: deletion of
  an old receipt must never let a replay create another service or reset credentials.

Round-two fixture tests cover protocol expectations, not these database locks,
cross-version races, key rotation, chain forks or retention behavior. Those need
implementation tests on the real transaction boundary.

## Activation and withdrawal: proposed authorization point

Agree that an exact GET or an expiring token alone cannot eliminate the race
between two independent database commits. Do not describe either as strict fencing.

Propose a CAF-owned durable activation authorization command, separate from approval
GET and credential acceptance. Radius first stages a disabled service. It then asks
CAF to authorize that exact source/company/franchise/customer/service request,
approval ID/revision/version and Radius activation-attempt UUID. CAF locks the
service's approval state and commits one immutable authorization decision plus
outbox record atomically. This commit is the proposed logical authorization point.

A withdrawal committed before this point causes denial. Matching retries return
the same decision; timeout means unknown until its decision receipt is read. CAF
outage or missing decision leaves the staged service disabled. Radius applies an
authorized decision at most once under its local service lock, with all configured
technical validity checks and no payment prerequisite. Local technical failure
does not imply successful internet activation or extend expiry on retry.

Withdrawal AFTER authorization is a later ordered lifecycle action, not proof that
the earlier authorization never happened. If Radius already knows a later revocation
before local enable, it must not enable using the earlier decision. But delivery
delay can still allow local enable after a later CAF withdrawal commit. This
protocol deliberately DOES NOT claim atomic wall-clock withdrawal/activation across
databases, and no bound can be promised during a network partition.

Before enabling this proposal, we need an explicit agreed requirement for that
post-authorization case. If the requirement is "no local activation after ANY CAF
withdrawal commit", this command protocol is insufficient. A durable distributed
prepare/commit/recovery design or changed authority boundary would be required,
including how withdrawals wait during uncertain outcomes. Do not hold a normal
database transaction open around an HTTP request and claim that solves crashes.

Please confirm whether the logical authorization point is an acceptable technical
model and specify withdrawal versus authorization ordering fixtures. Owner approval
is needed for any resulting user-visible withdrawal behavior or accepted race;
neither developer should choose that product behavior implicitly. Pending later
KYC review is a separate unresolved policy, not automatic approval withdrawal.
Unattended activation stays disabled until the full behavior is agreed and tested.

## Retention and recovery proposal

Propose configurable initial operational defaults: username hold 15 minutes,
materialized snapshot lifetime 24 hours, change feed retention 30 days. Advertise
server expiry in responses; these are engineering proposals awaiting CAF agreement,
not fixed user billing/plan rules. Renewal revalidates the binding and availability.
Snapshot construction plus reading plus catch-up must fit the retained watermark;
abort/restart if that coverage cannot be guaranteed. A 410 never means permission
to discard local service state or infer deletion from incomplete scope.

Credential ciphertext retention and receipt replay retention are separate from
username holds/feed TTL. CAF should propose its bounded credential recovery period;
purge immediately on durable acceptance. Keep service identity/accepted-credential
tombstones for the lifetime of the integration service relationship. Organization
and staff lifecycle schemas/recovery remain required before their unattended sync.

## Validation

Reran CAF's nine baseline tests and sixteen round-two tests at the exact reviewed
commit in an isolated ignored copy: 25 passed. No canonical v1 schemas were changed.
No runtime APIs, distributed fencing, production activation or deployment were
implemented by this review. Requested next work: CAF response on the authorization
model and linked canonical schema proposals for the accepted response/v2 envelope
shapes; independent CAF safety fixes and Radius foundations can proceed meanwhile.
