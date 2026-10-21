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
transactional rollback. Four additional MariaDB-only tests check the SQL view.
FreeRADIUS SQL/PAP configuration and separate database roles are implemented;
the disposable packet harness exercises actual upstream `radclient` requests
once run on Linux. Local application checks are not PPPoE sessions.

All 20 application/SQL tests passed on a portable MariaDB 11.8.9 instance, and
separate probes confirmed restricted database grants. No full acceptance check
above is complete. Docker is unavailable on the Windows host. Container builds,
FreeRADIUS validation, live AAA/accounting/Disconnect, recovery and capacity
measurement await Ubuntu validation and remaining accounting/dispatcher work.
See [development status](development.md) and the
[deployment runbook](lab-deployment.md).
