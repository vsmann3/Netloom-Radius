# CAF / Radius staged production rollout proposal

Status: planning only. No deployment, production settings/data change, or network
activation authorized by this document. Owner accepted the isolated STAGED model.

## Source and deployed evidence

Radius promoted main before this planning update:
`2ce33dc415225a5f57df0c3808c70e16e61f5910`; working model implementation/evidence
through `778b3b7`. CAF main independently confirmed remotely:
`d2a71e077d419a43f244fe7e068b5537710c41ab`, implementation `b9ad5b0`.
Local pair 18110/18120 and PostgreSQL18130 are demos, not deployment evidence.
Last recorded production checkout was `1e57699715fbaff7253e46ca11f122b8084ad5f9`;
running image SHA was not verified (interactive sudo required). Last recorded
catalog HTTP404 is historical, not a fresh live check. Current production image,
migration state and settings must be inventoried read-only before rollout.

## Minimal deliverable

One explicitly selected real company/franchise, existing CAF form, published
Radius plans, reservation, CAF company approval, durable outbox delivery, receipt
reconciliation, same lifetime customer ID, and SUSPENDED Radius service. No new
CAF form, demo fixture IDs, portable database, synthetic activation or live NAS
changes. This verifies production onboarding plumbing without granting internet.

## Required implementation before a deployment candidate

Radius owner:

- Add explicit Compose environment forwarding for CAF_PROVISIONING_ENABLED,
  CAF_FINGERPRINT_KEYS_FILE, CAF_FINGERPRINT_KEY_ID, CAF_FORM_URL and
  CAF_FORM_ALLOWED_ORIGINS. Add a protected read-only fingerprint key-ring secret
  mount; retain historical key versions for replay verification. Existing Compose
  forwards only catalog enable/proxy settings. Default all integration flags off.
- Extend audited owner-only setup tooling for exact franchise mappings and explicit
  expiring grants plans_read/reservations_write/provisionings_write/receipts_read,
  plus rotation/revocation. Current configure_caf_catalog issues plans_read only;
  do not use demo seed or ad-hoc SQL in production. Validate immutable mapping
  conflicts and write secrets only into protected new files.
- Produce pinned image/revision manifest, configuration validation/preflight,
  migration/backup/restore and staged rollback runbook. Verify the HTTPS proxy's
  actual container-visible peer address; trust only that address and overwrite
  X-Forwarded-Proto. Keep app port loopback-only.
- Add deployed-mode MariaDB/HTTPS integration verification, cross-company denial,
  disabled-state packet rejection, expired token/reservation, lost response/retry
  and operator recovery checks. Existing MariaDB CI is evidence, not live acceptance.

CAF owner (peer confirmation needed): replace demo-only database/config/API guards
with a separately gated, audited production STAGED mode using normal CAF database,
real scoped bindings, encrypted settings and production HTTPS allowlists. Keep the
same form/wire contract and fail closed by default. Package a supervised worker
with restart/backoff, health/queue-age monitoring, receipt-first retries, encryption
key management, absolute 24h secret expiry/purge and explicit unknown-acceptance
recovery. Confirm exact production paths/config and exclusion of historical fake
success records from automatic replay. Do not weaken demo guards to achieve this.

Joint: operational retention/reconciliation jobs and logs must expose IDs/status
without credential payloads. Confirm actual request-size/timeouts and existing
60 requests/minute per Radius token behavior against worker polling/load.

## Configuration and mappings

Use a stable agreed production source (for example caf-portal), real CAF company
and franchise IDs, and each existing Radius numeric company ID. No name matching,
implicit remapping or copied netloom-demo-* bindings. Inventory all three companies,
then owner chooses the first pilot and verifies its franchise/reviewer membership.
Issue a scoped expiring Radius bearer to CAF backend only. CAF read API credentials
are separate and must not be exposed to browsers; exact approval/authorization
reads are needed for the later activation implementation, not evidence that it
already exists. Select specific plans and explicitly publish each with
publish_caf_plan --actor PANEL_OWNER --plan-id UUID --duration-seconds SECONDS.
No assumed calendar month, inferred price or automatic publication of every plan.
Live plan edits require deliberate versioned republishing.

## Proposed rollout sequence and checkpoints

1. Implement above code/config/runbooks via reviewable changes. Test against an
   independent production-like MariaDB/CAF database over HTTPS with STAGED mode.
   Ask Vikas to test; await feedback before accepting the new milestone.
2. After separate deployment authorization, read-only inventory actual images,
   migration state, proxy/network configuration and mappings. Back up both apps'
   databases and required encryption/fingerprint keys; verify isolated restore.
3. Deploy pinned code with integrations OFF. Apply pending Radius migrations up
   through0010 via migration role (0009/0010 include immutable-binding trigger
   work;0010 is deliberately non-atomic for MariaDB DDL). CAF owns its own Prisma
   migrations and reviewed backfill policy. Verify existing login/RADIUS behavior.
4. Configure one pilot binding/franchise, protected keys, HTTPS origins and explicit
   publications. Enable catalog only; CAF fetches real scoped plans. Owner checks.
5. Separately enable STAGED reservation/provisioning and CAF supervised worker for
   pilot only. Use controlled owner-approved test records/proofs. Confirm no Radius
   subscriber before approval, reviewer scope, one accepted suspended service per
   request, same customer ID, secret purge, no reset/duplicate after replay, second
   connection under same ID and rejection for unauthorized tenant/network access.
6. Ask Vikas to test public same-form journey, PDF, return link, ID search and staged
   statuses. Await acceptance before expanding to the other two companies.

Radius has no background worker in this STAGED slice: its endpoints commit
synchronously and persist receipts. CAF owns transport/outbox worker. A future
Radius authorization/withdrawal consumer and operational scheduler are separate.
For rollback stop CAF delivery and disable Radius integration flags/revoke token;
retain accepted services/receipts and key versions. Do not blindly reverse schema,
restore stale databases or replay with new identities; reconcile unknown delivery
outcomes before resuming. Never reset accepted credentials as a retry strategy.

## Decisions before actual internet activation

Owner must choose authorization/withdrawal semantics: under the proposed durable
CAF authorization logical point, a later withdrawal unknown during a partition can
allow enablement. That is not strict wall-clock fencing. Alternatively require a
stronger shared fencing design; implement/test it before unattended activation.
Also choose whether existing approved service continues during later pending KYC.
Initial service must always require approval. Radius billing/network-only edits do
not require CAF KYC approval. Owners must select pilot NAS/access method, account
expiry anchor and plan validity, and approve operational suspension/revocation and
recovery behavior. Production activation code is NOT implemented by the demo.
Accounting, Disconnect/CoA, static IP/hotspot, wallets/commissions and billing remain
separate product work; STAGED pilot acceptance does not claim these are ready.
