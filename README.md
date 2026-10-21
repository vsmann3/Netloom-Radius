# Netloom Radius

Multi-tenant ISP authentication and subscriber management, starting with our own ISP as the first tenant.

## Status

The first application foundation is implemented: tenant-aware Django models,
membership-based management access, suspension auditing/outbox, migrations and a
pinned Docker Compose lab configuration. All 21 application/SQL tests pass against
MariaDB 11.8.9, including database tenant constraints and restricted-grant checks.
FreeRADIUS uses its stock SQL and PAP modules with tenant-qualified authorization
and a read-only database account. A disposable packet-test harness is included.
Linux CI has passed container startup and synthetic RADIUS authentication,
tenant-isolation, rejection and database-outage checks. The separate staging VM
and real MikroTik acceptance still need validation. Accounting writes and
Disconnect dispatch remain pending.

## Agreed foundation

- FreeRADIUS 3.2.x for authentication, accounting and Disconnect/CoA.
- MikroTik PPPoE NAS initially; Accel-PPP on a separate Linux BNG later.
- MariaDB for application and RADIUS data, with separate database users and permissions.
- Custom Django panel and API; Django 5.2 LTS is the initial framework target.
- Ubuntu Server LTS guest on Proxmox, with Docker Compose for application services; Debian 13 is also supported by host preparation.
- Support shared multi-tenant installations and dedicated ISP installations from the same codebase.
- Public GitHub repository: [vsmann3/Netloom-Radius](https://github.com/vsmann3/Netloom-Radius).
- Separate Ubuntu VMs: staging at `103.215.107.181`, production at `103.215.107.180`.

Python dependencies are pinned in `requirements.txt`. Verified container tags and
registry digests are recorded in `image-lock.env`; the Compose wrapper loads that
file along with local deployment settings.

## Start here

1. Provision the VM using [the Proxmox guide](docs/proxmox-lab.md).
2. Read [the architecture decisions](docs/architecture.md).
3. Follow [the first milestone acceptance checklist](docs/milestone-1.md).
4. Deploy the foundation using [the lab runbook](docs/lab-deployment.md).
5. See [implementation status and local tests](docs/development.md).
6. Follow [the staging-to-production workflow](docs/staging-production.md) and [release policy](RELEASE_POLICY.md).

Do not commit credentials, subscriber data, database dumps or private keys. Git distributes code and configuration templates; deployment-specific secrets and data stay outside Git.

Commercial licensing for original Netloom code has not been selected. Upstream components retain their own licenses; using them does not automatically determine the license of every independent component in this repository.
