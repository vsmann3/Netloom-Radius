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

The first pilot company and owner memberships are not yet specified. These names
are onboarding requirements, not confirmation that live tenants have been created.

Operate the user's three companies first. Each company is a tenant with separate
subscribers, NAS registrations, plans, staff permissions and finances. Central staff
may receive explicit memberships across companies; no implicit superuser access.
Each company needs multiple franchises with customer ownership, staff permissions,
wallets, recharge balances, commission/revenue sharing and settlements.
Every company and franchise must have an automatically assigned permanent numeric
public ID of at least five digits. Keep UUID relationships internally and use public
numbers in browser company URLs; see company-numbers.md.

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
