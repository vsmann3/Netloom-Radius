# Product direction - 2026-10-22

The user confirmed Django development after reviewing build-versus-reuse tradeoffs.
This supersedes the temporary pause in docs/reuse-first.md. Use existing maintained
components where useful; keep upstream FreeRADIUS unchanged.

## Purpose and boundaries

Confirmed company names:

| Company | Proposed tenant slug |
| --- | --- |
| Infolink Broadband | `infolink-broadband` |
| NorthNet | `northnet` |
| VM Net | `vm-net` |

All three companies were onboarded on the VM with explicit owner memberships for
the existing panel account suradmin. The first live network pilot is not selected.

Operate the user's three companies first. Each company is a tenant with separate
subscribers, NAS registrations, plans, staff permissions and finances. Central staff
may receive explicit memberships across companies; no implicit superuser access.
Each company needs multiple franchises with customer ownership, staff permissions,
wallets, recharge balances, commission/revenue sharing and settlements.
Every company and franchise must have an automatically assigned permanent numeric
public ID of at least five digits. Keep UUID relationships internally and use public
numbers in browser company URLs; see company-numbers.md.

Customer onboarding/eCAF is owned exclusively by the separate caf-portal project.
Reuse its unique 10-digit customerId as the main customer identifier in Radius;
do not build eCAF forms or a competing customer-number allocator here. Company and
franchise public IDs are distinct from customer IDs. See integrations/ecaf-api-contract.md
for the proposed API-only boundary and developer handoff.

Confirmed onboarding journeys: CAF fetches company-scoped plans from Radius,
assigns username and initial password, then provisions Radius after CAF approval.
No additional payment/wallet gate applies to initial internet activation. Radius
reserves/validates usernames and stores PAP-compatible password hashes. Add customer
from Radius opens the same CAF form in a new tab with safe context/return navigation.
CAF handles self-service. The same 10-digit customer ID is retained for all customer
operations; local service UUIDs distinguish connections without renumbering customers.

Validate on the user's network before offering the same codebase to fellow ISPs
for paid hosting, setup, support or software access. Separate installations remain
an option. Defer automated licensing and a commercial sales portal.

## Delivery order

1. Tenant-scoped management of plans, subscribers and NAS registrations.
2. Accounting ingestion and reliable Disconnect dispatch; synthetic then real NAS
   acceptance before enabling subscriber traffic.
3. Franchise ownership/roles and financial ledgers, recharge, commissions, reversal
   and settlement workflows, with concurrency and isolation checks.
4. Pilot one company and a small franchise group; verify backups/restores and
   reconciliation, then expand to the other companies.
5. External ISP onboarding after internal operational acceptance.

Company names, memberships and commercial split rules must come from the user;
do not invent live companies, money movements or franchise balances.

## First management increment

Company pages list plans and paginate subscribers in pages of 100. Owners/operators can create
plans and subscribers; viewers can read. Creation and audit commit together.
Subscriber plan choices are restricted to the company. New subscriber credentials
are unusable until provisioned with the existing hidden-prompt password command.
Company owners can register disabled NAS devices. The server generates external
secret references; shared secrets and activation stay outside the panel. Subscriber
suspension uses the audited outbox service; active-session dispatch remains pending.
No finance, franchise, edit/delete or live NAS activation is implied by this page.
