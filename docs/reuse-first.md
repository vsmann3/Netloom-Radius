# Reuse-first direction - 2026-10-22

The user does not want to develop a new ISP software product. Assemble established
software, configure it, and maintain small necessary improvements. This supersedes
the earlier assumption that a custom Django management product is the target.

## Direction

User clarification: keep daloRADIUS under active consideration. Prefer extending
it with maintained open-source modules or a companion application over dropping
it because franchise finance is absent upstream. No decision to abandon daloRADIUS
has been made. Evaluate the integration effort explicitly before implementation.

- Keep upstream FreeRADIUS as the AAA engine.
- Evaluate daloRADIUS as the management application before any further Django
  management feature development. A maintained fork is acceptable if needed.
- Separate ISP installations/databases are acceptable; a shared tenant database
  is not a requirement worth a large rewrite.
- Multiple franchises within an ISP are mandatory. Separate ISP installations
  alone do not establish franchise support.
- A commercial subscription/managed-service entitlement mechanism may be evaluated
  separately. Do not assume upstream software can become exclusive proprietary
  software, or couple subscription expiry to subscriber authentication outages.
- Preserve the existing deployment and data while evaluating a replacement.

## Initial source review

Reviewed upstream https://github.com/lirantal/daloradius at
ace45161041f8ccd7ebfced6217ed7a7c53457d0 (local ignored review checkout).

Operator ACLs grant page access. CONFIG_LOCATIONS supports selecting database
connections. Neither establishes a franchise hierarchy or isolation between
franchise customer portfolios. The subscriber report builder inspected uses
username-based joins; this is a targeted initial review, not a full audit.
Franchise wallets, commissions and recharge balances are not verified in daloRADIUS.

## Confirmed franchise scope - 2026-10-22

The user explicitly requires franchise wallets, recharge balances, commissions and
revenue sharing, in addition to isolated customer/staff management. These are
mandatory selection criteria, not optional future custom development.

Initial vendor-documentation leads (not accepted or independently validated):
- DMA Radius Manager: official manual documents reseller balances, prepaid refills,
  manager permissions and restrictions on access to all users/invoices.
  https://www.dmasoftlab.com/documents/user_manual.pdf
- Splynx: official configuration guide documents partners with scoped access,
  customers, tariffs, routers and commission percentages. The required franchise
  wallet debit/reversal workflow remains unverified.
  https://deploy.splynx.com/basic-configuration/initial-steps/
- ISPRadius: vendor explicitly advertises franchise wallets, recharge and revenue
  sharing. Operational maturity, support, ledger correctness and FreeRADIUS
  compatibility remain unverified; marketing is not acceptance evidence.
  https://ispradius.net/isp-billing-software/

Require a two-franchise demonstration including wallet top-up, renewal debit,
commission split, insufficient balance, duplicate renewal prevention, refund/reversal,
settlement and cross-franchise access denial. Verify deployment, export/backup,
upstream engine compatibility and managed-service/resale terms before selection.

References:
- https://github.com/lirantal/daloradius/blob/master/README.md
- https://github.com/lirantal/daloradius/blob/master/app/common/includes/daloradius.conf.php.sample
- https://github.com/lirantal/daloradius/blob/master/app/operators/library/check_operator_perm.php
- https://github.com/lirantal/daloradius/blob/master/app/operators/library/operator_reports_pdo.php

## Acceptance before choosing the management application

1. ISP administrator can oversee at least two franchises.
2. Franchise staff can manage only their assigned customers; direct URLs, edits,
   accounting, reports, exports and Disconnect cannot cross that boundary.
3. Demonstrate mandatory wallets, commissions/revenue sharing and recharge balances.
4. Demonstrate MikroTik subscriber creation, plans, expiry, accounting and Disconnect.
5. If daloRADIUS requires substantial business feature development, compare existing
   franchise-ready ISP platforms instead of automatically starting another rewrite.

No replacement, migration, public fork or licensing mechanism has been deployed.

## Open-source composition candidate

daloRADIUS + FreeRADIUS for access management, with ERPNext as a candidate for
invoices, financial ledgers and sales-partner commission calculation. ERPNext's
commission field does not itself create/pay a payable; settlement needs an explicit
accounting workflow. Its ledger/advances are not automatically an ISP franchise
wallet with atomic renewal authorization.

https://docs.frappe.io/erpnext/sales-partner
https://docs.frappe.io/erpnext/payment_ledger

No maintained drop-in daloRADIUS franchise-wallet/commission module has been
verified. A companion integration would still need franchise authorization,
available-balance reservation/debit, idempotent provisioning, failure compensation
and reconciliation. Avoid two independently editable financial balances. Confirm
supported daloRADIUS integration surfaces before choosing API versus an adapter.
