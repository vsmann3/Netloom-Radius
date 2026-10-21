# Milestone 1: repeatable single-node lab

## Deliverables

- Version-pinned FreeRADIUS 3.2.x, MariaDB and minimal Django service configuration.
- Docker Compose deployment and repeatable Ubuntu LTS host preparation.
- Versioned schema migrations, a development tenant and explicit opt-in synthetic test subscribers.
- Tenant-aware NAS and subscriber resolution with documented authentication-method support.
- Authentication, accounting and Disconnect checks, plus deployment and recovery instructions.

## Acceptance checks

1. A fresh Ubuntu LTS VM can deploy from a documented Git revision without manual database edits.
2. FreeRADIUS configuration validation succeeds before serving requests.
3. Correct credentials authenticate; wrong passwords, unknown NAS devices, suspended and expired subscriptions fail as intended.
4. Two tenants can use the same subscriber username without crossing tenant boundaries, including with different passwords and plans.
5. One real MikroTik completes PPPoE login and enforces the configured upload/download speeds.
6. Start, Interim and Stop accounting records retain the correct tenant and NAS; duplicate packets do not produce duplicate logical sessions.
7. A targeted Disconnect terminates the intended session, records its result and cannot target another tenant's router.
8. Restarting services preserves data; a database backup can restore into a clean lab instance.
9. A synthetic 500-subscriber workload measures authentication latency, reconnect bursts and accounting load. Synthetic checks and actual PPPoE sessions are reported separately.
10. Database and management access restrictions are tested from an unauthorized network location.

At a 300-second interim interval, 500 active subscribers average approximately 1.67 interim updates per second. Burst behavior, authentication policy and storage latency still require measurement.

## Deferred work

Billing, payment integrations, eCAF integration, Accel-PPP, IPoE, monitoring integration and multi-node availability follow the initial MikroTik lab. Tenant isolation is part of this first milestone, not a later retrofit.

## Implementation checkpoint: 2026-10-21

The management foundation, schema migrations, tenant ownership constraints,
suspension transaction/outbox and Compose/runbook files are implemented.
Sixteen local SQLite application tests pass, including direct cross-tenant
writes, authorization, CSRF, audited password provisioning, client rendering and
transactional rollback. Five additional MariaDB-only tests check the SQL view and deployed driver queries.
FreeRADIUS SQL/PAP configuration and separate database roles are implemented;
the disposable packet harness exercises actual upstream `radclient` requests
on Linux. These automated packet checks are not PPPoE sessions.

All 21 application/SQL tests and the synthetic FreeRADIUS packet suite passed
on GitHub's Ubuntu runner with the pinned images. This validates configuration,
authentication, isolation and restricted grants in CI. Milestone 1 is not complete:
actual VM deployment, real MikroTik PPPoE, accounting/Disconnect, recovery and
capacity measurement remain pending.
See [development status](development.md) and the
[deployment runbook](lab-deployment.md).
