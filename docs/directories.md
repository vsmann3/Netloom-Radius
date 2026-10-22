# Dedicated management directories

Each company has separate pages:
- `/companies/NUMBER/` - company overview and scoped counts.
- `/companies/NUMBER/users/` - subscriber account directory.
- `/companies/NUMBER/plans/` - service plans and creation form.
- `/companies/NUMBER/routers/` - NAS registrations and owner-only creation form.

The sidebar links to pages, not sections on one long screen. Old overview fragments
such as `#routers` and `#subscribers` redirect with a small local compatibility script.
Existing UUID/company POST endpoints remain authorized for already-open forms.

## Subscriber filters

- Exact account UUID; case-insensitive partial username search.
- Provisioning status, plan and expiry validity (not expired, expired, next 7 days).
- Inclusive UTC date ranges for expiry, account creation and last recorded renewal.
- Recorded/unrecorded renewal state.
- Username, expiry or creation sorting, and 25/50/100 rows per page.

Filters combine, are validated server-side, and stay applied when paging. Invalid
inputs return an empty directory with errors instead of silently broadening results.
Plan choices, counts and records remain scoped to the authorized company. A foreign
account ID does not reveal its owner; a foreign plan ID is not an allowed choice.

Subscriber Account ID in the current directory means the existing UUID. The user
subsequently chose the CAF portal's 10-digit customerId as the shared main customer
identifier. That supersedes generating another customer number here. Integration
will add/display/filter this external ID while retaining local UUID service IDs;
it is not populated by the present directory release. See integrations/ecaf-api-contract.md.

## Renewal dates

Migration 0005 adds nullable last_renewed_at. Existing records remain unknown and
display “Not recorded”. No renewal date is inferred from expiry/creation. The
audited renewal/payment workflow remains pending; these fields do not implement it
or provide full renewal transaction history. Migration 0006 indexes company/date
lookups for expiry, creation and last renewal.

## Validation

Local suite: 50 tests, 44 passed and 6 MariaDB-only skips. New checks cover dedicated
navigation, filter combinations, date boundaries, malformed values, sorting,
paging, viewer access and cross-company denial. Existing database ownership checks
still pass with the schema additions.

Disposable headless Chrome checks verified separate page navigation, plan and
subscriber creation, filtering, no-match/reset behavior, unique form IDs and old
fragment navigation. Desktop/mobile screenshots were inspected; the document has
no horizontal overflow (wide tables scroll within their own container).
