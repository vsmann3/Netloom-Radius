# Architecture decisions

## Product and deployment

One codebase supports multiple ISPs on a shared installation and dedicated installations for individual ISPs. An installation is a deployment boundary; a tenant is an ISP business boundary. A dedicated deployment still uses the same tenant-aware data model.

Start with one FreeRADIUS node, one MariaDB instance and a minimal Django management application on the lab VM. Validate MikroTik first. Add Accel-PPP, a second RADIUS node, database recovery and replication in later milestones. Replication alone is neither backup nor automatic failover.

## Tenant isolation

Every business record must belong to a tenant, including customers, subscriptions, plans, invoices, payments, NAS registrations, accounting attribution and queued router actions. User memberships explicitly grant roles in a tenant. Platform access is separate, restricted and audited.

Enforce ownership in request authorization, database constraints, background jobs, exports and API lookups. Do not rely on a UI tenant selector or application query filtering alone. Tests must deliberately attempt cross-tenant access.

RADIUS must determine tenant identity through trusted NAS registration before subscriber lookup. Never trust a tenant identifier supplied by a subscriber. An unknown NAS must not fall back to a default tenant.

Subscriber names are unique within a tenant, not across the installation. Before implementing SQL authorization, choose and test a tenant-qualified internal identity mapping. A stock username-only FreeRADIUS SQL configuration is insufficient for this product. Any internal rewrite must preserve the identity and protocol requirements of PAP, CHAP and MSCHAP as applicable; do not assume rewriting User-Name is harmless.

Accounting lookup must include tenant and NAS context as well as session identifiers. Validate reconnects, duplicate packets, missing Stop records, NAS restarts and Accounting-On/Off behavior.

## Data and AAA

Keep upstream FreeRADIUS core unchanged. Implement policy with supported modules, SQL queries and unlang. The application owns business state and controlled RADIUS provisioning; authentication reads the resulting policy through a restricted database account. Accounting writes have narrowly scoped permissions.

Schema extensions and queries must be versioned together. Preserve upstream-compatible RADIUS tables where practical, but compatibility does not override tenant isolation. Do not expose generic database editing in the ISP-facing panel.

Administrative state changes and router actions need a durable job/outbox boundary. Persist the business change and action request atomically, then dispatch with retries and recorded results. A suspension must remain effective for subsequent authentication even if immediate Disconnect fails.

Resolve a router action's tenant, NAS address, secret and active session from trusted database records. Never accept an arbitrary destination or shell command from a panel user. Validate NAS-specific support before offering live speed changes; reauthentication can be required.

## Security and operations

Use unique NAS secrets, separate service credentials and deployment-specific secret files. RADIUS/UDP traffic should traverse trusted private networks or protected tunnels. Subscriber password storage policy and required PPP authentication methods must be decided before production; plaintext-equivalent credentials must not appear in logs or exports.

Record actor, tenant, target, timestamp and outcome for administrative changes. Keep customer personal data out of application logs. Define applicable Indian retention obligations and tenant contracts before production retention settings are finalized.

Deploy from reviewed Git revisions with pinned dependencies, migrations, backups and documented rollback procedures. Never run destructive seed routines on upgrade.

## CAF integration boundary (user decision, 2026-10-22)

The separate https://github.com/vsmann3/caf-portal application owns eCAF capture,
documents, review and 10-digit customer ID issuance. Do not implement another eCAF
form or document store in Radius. Radius owns AAA/network service management and
the previously agreed operational/financial workflows. Integrate only through
authenticated, tenant/franchise-scoped APIs; never share databases or browser logins.

CAF customerId is the shared main customer identifier, transported as a 10-digit
string and never independently allocated here. Internal subscriber UUIDs identify
network services; company/franchise numbers remain separate organizational IDs.
Reviewed CAF source at 05dbe819ff52a5fb022965a1113bd94981b2f167. The existing adapter
is a no-op, not an implemented connection. The proposed endpoint/payload/retry
contract is in [CAF integration](integrations/ecaf-api-contract.md); it must be
agreed and implemented by both developers before enabling sync.
