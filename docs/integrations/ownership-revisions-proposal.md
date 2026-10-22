# Proposed onboarding ownership and revision approval

Status: ownership expansion and approval scope confirmed by the user. CAF approval
applies ONLY to changes in basic customer/KYC information requiring review under
CAF rules. Radius-owned billing/network/service operations, including username
and password changes, do not need CAF approval. The existing-access policy while
a later KYC revision is pending remains unresolved; do not implement that policy
without confirmation. Integration runtime remains unimplemented.

## Ownership

CAF is the onboarding master for companies, franchises, staff/operators and
customers. Radius consumes approved identity/organization events and maps them
to internal tenant/franchise records and scoped operational permissions. Do not
build competing onboarding forms for these entities in Radius.

Radius is authoritative for service/network configuration (plans, plan changes,
static IP assignments, PPPoE/hotspot settings, NAS devices, accounting, sessions,
Disconnect) and operational billing, wallets, renewals and commission workflows.
These capabilities are product scope, not a claim they are implemented today.
Currently only the PAP/MikroTik foundation and initial management pages exist;
hotspot/static-IP/billing/franchise runtime features remain to be built/accepted.

Radius publishes safe service/billing summaries to CAF as read-only projections.
CAF read-only access must be enforced by API scopes/field ownership, not just UI.
The confirmed new-onboarding CAF plan selector still reads Radius's plan catalog;
its approved plan request is a provisioning request, not authority to edit plans.

## Editing CAF-owned information from Radius

Radius may provide an edit entry point, but does not overwrite the approved CAF
record or its database. Submit an authenticated change request to CAF containing:
change_request_id, customer_id, service_id where relevant, base approved revision,
actor reference, mapped company/franchise, proposed field changes and reason.

CAF validates scope and allowed fields, creates a pending revision, preserves the
last approved snapshot and presents the revision/diff to the eCAF manager. Its
callback/change-feed event must identify the same change request and exact revision.
Radius applies the change only on approval, atomically with local audit/outbox.
Rejection leaves the approved configuration intact. Stale/duplicate decisions
cannot approve a different payload or a newer revision.

Proposed states: pending_review -> approved -> applying -> applied, or rejected;
application failure is separately visible/retryable, not falsely marked active.
Both UIs show CAF review status and Radius application status independently.

Username/password changes are Radius-owned service operations and apply under
Radius authorization/audit without CAF approval. Publish the username and safe
change-status metadata as needed, never the password/hash. CAF's read-only network
projection never receives passwords, hashes or NAS secrets. This does not supersede
the confirmed initial CAF-to-Radius credential delivery.

## Policies requiring user confirmation

1. While a revision is pending for an already-approved active service, keep the
   last approved configuration working (recommended) or suspend until approval?
   Existing suspension/expiry continues to apply; a pending request grants no access.

Confirmed scope: only basic customer/KYC fields that CAF requires to be reviewed
(e.g. name/full name and its designated KYC fields) create a pending CAF revision.
CAF defines/validates the exact field policy; Radius must not guess or maintain a
competing list. All Radius-owned operations (billing, renewals, credentials, plan,
IP/mode/network changes) use Radius permissions/audit and sync read-only summaries
to CAF. No pending KYC revision is created for those operational changes.

New/unapproved accounts remain without internet until initial CAF approval, as
already confirmed. The two open policies concern later changes, not initial access.

## API expansion after agreement

- CAF: organization/staff approval events, scoped change-request submission,
  pending revision/diff reads, decision events and reconciliation feed.
- Radius: consume organization/staff mappings with explicit role policy; receive
  revision decisions; publish safe service/billing projections to CAF.
- Keep identity revision, service configuration version and financial transaction
  IDs separate. All share the same permanent 10-digit customer ID where applicable.
- Staff identity onboarding does not mean copying login passwords across systems.
  Choose shared identity/SSO separately; apply mapped Radius permissions explicitly.
