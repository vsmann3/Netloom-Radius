# Development and current implementation

## Management increment - 2026-10-22

Local company pages now list plans/subscribers and allow owners/operators to create
them with atomic audit records. Viewer access is read-only; plan selection and
records are tenant-scoped. New credentials are disabled until the existing password
command provisions them. Owners can register NAS devices, initially disabled, with
server-generated secret references; the panel never accepts a shared secret.
Subscribers are paginated and can be suspended through CSRF-protected forms that
use the existing audited suspension/outbox service. Disconnect delivery remains
pending. This increment is not deployed yet. Local suite: 31 tests,
26 passed and 5 MariaDB-only tests skipped; no model migration required.
See [confirmed product direction](product-direction.md) for the three-company and
franchise rollout scope. Historical feature-status wording below predates this increment.

## Implemented foundation

- Django 5.2.18 with session login, a minimal ISP membership page, a scoped subscriber-list API and a CSRF-protected suspension API.
- Tenants, memberships, plans, subscribers, registered NAS devices, sessions, audit events and a durable Disconnect outbox.
- Composite MariaDB foreign keys prevent cross-tenant plan, session and action references even through direct writes. These were tested against MariaDB 11.8.9; SQLite tests use equivalent ownership triggers.
- Subscriber usernames are unique per ISP. Policy looks up the tenant by registered NAS source address and never rewrites the username. Source addresses are globally unique.
- Stock FreeRADIUS `rlm_sql_mysql` and `rlm_pap` configuration with a versioned authorization view. The temporary Python password verifier has been removed. The view maps Django PBKDF2-SHA256 hashes into FreeRADIUS's supported format; upstream core remains unchanged. CHAP, MSCHAP and EAP are explicitly rejected.
- The SQL queries select by received packet source address and exact username. Replies contain the MikroTik rate limit, expiry-bounded Session-Timeout and a 300-second accounting interval.
- Separate database users: `netloom_migrate` owns schema migrations, `netloom_app` has application DML without DDL, and `netloom_radius` can SELECT only the authorization view. A hidden-prompt command provisions subscriber passwords with audit; a renderer generates registered NAS clients from external secret files.
- Atomic, idempotent suspension persists its audit event and Disconnect requests together. A queued request does not yet send a packet; the dispatcher is pending.
- Opt-in synthetic seed data has unusable passwords and preserves existing records on repeat runs.
- Compose configuration, immutable base-image digests, generated secret files, a persistent database volume, a SQL/PAP FreeRADIUS profile, host preparation and a database backup script. UDP ports stay unpublished until packet validation. Accounting is deliberately unacknowledged until tenant-safe writes are implemented.

The panel is deliberately minimal. There is no ISP-facing database editor, billing, customer onboarding or browser credential editor yet. Platform superuser status does not grant access to an ISP; explicit membership is required.

## Local checks (Windows or Linux)

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe manage.py check --settings=netloom.test_settings
./.venv/Scripts/python.exe manage.py test core --settings=netloom.test_settings -v 2
./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=netloom.test_settings
```

On Linux use `.venv/bin/python`. Test settings select SQLite and a fast hasher for management fixtures; PAP-specific commands explicitly use PBKDF2. Five SQL-specific tests run only against MariaDB and are skipped on SQLite. All 21 tests and the synthetic upstream `radclient` packet suite passed on GitHub's Ubuntu runner with pinned container images. [First passing integration run](https://github.com/vsmann3/Netloom-Radius/actions/runs/39641740749). Target-VM and real MikroTik validation remain pending. Never use test settings for a deployment.

## Disposable SQL/PAP packet checks

On the Ubuntu VM with Docker Engine and Compose:

```sh
sudo python3 scripts/test_radius.py
```

This creates a random Compose project, fresh database volume and temporary generated credentials. It publishes no host ports and does not use the lab's normal volume or secrets. Its `finally` block removes only that disposable project's resources. It builds `netloom-app:radius-test`; `--skip-build` reuses that image after a successful build. Failure diagnostics redact generated secrets and credential attributes before printing. The normal VM startup command validates configuration before serving; customer authentication does not run with debug logging enabled.

Checks use upstream `radclient`: same-name subscribers in two tenants with different passwords/plans; wrong passwords; unknown/case-mismatched users; suspended, expired and unusable credentials; disabled NAS/tenants; NAS-IP-Address spoofing; unsupported methods; missing Message-Authenticator; unknown clients; database privilege denials; Django tests on MariaDB; suspension isolation; and database outage. These are synthetic RADIUS packets, not PPPoE sessions or a capacity benchmark.

## Tenant and credential rules

Use a single canonical subscriber spelling. MariaDB reserves case variants within a tenant; the SQL query additionally requires exact spelling. Usernames in separate tenants may match.

Only PAP is enabled. Current credentials are PBKDF2-SHA256 with a 1–32 character alphanumeric salt and 100,000–2,000,000 iterations. Provisioning uses Django's default work factor. Unsupported/malformed hashes are excluded from the authorization view. No plaintext-equivalent credential is stored for CHAP/MSCHAP. SQL uses FreeRADIUS's trusted Packet-Src-IP-Address, never a subscriber-selected tenant, NAS-Identifier or NAS-IP-Address. No default tenant is permitted.

SQL supplies the hash through upstream PAP's preferred `Password-With-Header`
normalization using `{X-PBKDF2}`. This sets PAP's authentication type through the
existing module without custom password verification. Reply-query UNION values
use an explicit UTF-8 collation so the driver's connection collation cannot cause
authentication to fail; a regression test executes the deployed queries under
both Latin-1 and UTF-8 client settings.

NAS secrets are external file references, not database values. Rendering requires unique 64-character lowercase hex secrets, validates addresses/references and blocks directory traversal. Clients require Message-Authenticator; verify RouterOS compatibility before live use. Disabled NAS records immediately lose SQL authorization even if an older client entry remains loaded. Client additions and secret rotations require a validated restart. The initial loopback probe has no NAS registration and cannot authenticate.

Session identity includes tenant, NAS, boot epoch and session ID. The accounting implementation must establish boot epochs and handle duplicate/out-of-order packets before real sessions are stored.

## Remaining work before MikroTik acceptance

1. Build and start the pinned images on Ubuntu; run migrations and the same isolation tests against MariaDB.
2. Execute the disposable FreeRADIUS SQL/PAP harness, including restricted-grant checks.
3. Render reviewed NAS clients and validate FreeRADIUS before opening NAS-only UDP listeners.
4. Implement Start/Interim/Stop, NAS reboot handling, duplicate/out-of-order delivery, and byte-counter rollover tests.
5. Implement and test the outbox dispatcher, bounded retries, router timeouts and tenant-scoped Disconnect results. Do not represent pending rows as successful disconnects.
6. Finish recovery testing, the 500-subscriber synthetic workload and unauthorized-network checks, then test real MikroTik PPPoE and rate enforcement.

## Dependency verification

Versions were checked on 2026-10-21. Python package pins resolve through PyPI. `scripts/lock_images.py` resolved the Python, MariaDB and FreeRADIUS tags against Docker Registry to produce `image-lock.env`. Run that script only when deliberately reviewing an image update; normal deployment uses the checked-in digests.

Upstream references: [Django supported versions](https://www.djangoproject.com/download/), [MariaDB releases](https://mariadb.org/), [FreeRADIUS 3.2.10](https://github.com/FreeRADIUS/freeradius-server/releases/tag/release_3_2_10), [FreeRADIUS image usage](https://github.com/FreeRADIUS/freeradius-server/blob/release_3_2_10/scripts/docker/README.md), [Docker on Debian](https://docs.docker.com/engine/install/debian/).

Integration references: [upstream PAP formats](https://github.com/FreeRADIUS/freeradius-server/blob/release_3_2_10/src/modules/rlm_pap/rlm_pap.c), [SQL module](https://github.com/FreeRADIUS/freeradius-server/blob/release_3_2_10/raddb/mods-available/sql), [MySQL query format](https://github.com/FreeRADIUS/freeradius-server/blob/release_3_2_10/raddb/mods-config/sql/main/mysql/queries.conf).
