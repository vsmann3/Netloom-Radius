# Work checkpoint

Updated 2026-10-21. The user selected Ubuntu for the Proxmox VM and supplied
`radius.netnoc.in` with VM/public SSH address `103.215.107.180`. SSH username/port,
key enrollment and the installed Ubuntu release are pending. Staging must use a
separate VM at `103.215.107.181`. The user authorized creating the public repository
`vsmann3/Netloom-Radius`; that repository has now been created. No remote VM deployment
has been performed. Details are in `docs/deployment-target.md`.

## Completed

- Built the first Django management/data foundation, migrations and tenant foreign keys.
- Added 20 application/SQL tests covering isolation, authorization, CSRF, password provisioning, client rendering, SQL policy and outbox rollback.
- Added pinned Python dependencies and registry-resolved immutable image digests.
- Added Compose, Debian preparation, secret initialization, backup and lab runbook.
- Replaced the baseline with upstream FreeRADIUS SQL/PAP configuration, a tenant-qualified authorization view and separate database accounts. Removed the temporary Python password verifier.
- Added audited hidden-prompt subscriber password provisioning and a NAS client renderer backed by external unique secrets.
- Added a disposable Compose/`radclient` packet harness; it publishes no host ports.

## Validation

Local Python 3.14 / Django 5.2.18: 16 SQLite tests pass, with four MariaDB-only
tests skipped. All 20 tests passed against a checksum-verified portable MariaDB
11.8.9 on Windows, including actual composite foreign keys, authorization view,
PBKDF2 digest/salt/round projection and live status filtering. Separate probes
confirmed the RADIUS account cannot read subscriber tables, write business state
or create tables, and the application account cannot create tables. The portable
test server was stopped; no Windows service was installed. Download/test files
remain ignored under `.tools/` and `.dependency-check/`.

Django checks and migration consistency pass; both Compose YAML files parse and
port-exposure assertions pass. Production Python is pinned to 3.13.16. Neither
Docker nor WSL was installed on this host. Container entrypoints, FreeRADIUS
configuration parsing and actual RADIUS packets still require Linux validation.

## Resume here

The user requires all maintained source/templates/migrations/tests to be uploaded
to the public `vsmann3/Netloom-Radius` repository, with VM deployments fetched from GitHub.
Changes must pass CI and deployed staging validation before promotion from
`staging` to `main`. Local Git now has a policy-only `main` bootstrap and an
implementation `staging` branch. The CI workflow and separate staging/production
Compose project/image/port templates are prepared; no remote push has occurred.

The repository selection is resolved: the user explicitly requested a new public
`vsmann3/Netloom-Radius`. It was created via the authenticated GitHub CLI. Leave
the existing empty private `vsmann3/libre-radius` untouched.

The proposed staging hostname is `staging-radius.netnoc.in` on `103.215.107.181`;
the user has been asked to confirm/create its DNS. Branch protections and CI
execution have not been configured remotely or verified yet. See
`docs/staging-production.md`.

1. Obtain SSH username/port/key enrollment for both `.180` and `.181`, the installed
   Ubuntu release and MikroTik source IP/version. Follow `docs/lab-deployment.md`.
2. Run `sudo python3 scripts/test_radius.py` on Ubuntu. It exercises stock
   FreeRADIUS SQL/PAP with same-name subscribers in two tenants, rejection cases,
   NAS attribute spoofing, privilege denials and database outage; it cleans up
   only its randomly named disposable project. This harness has not run yet.
3. Deploy the normal lab and validate `sudo sh scripts/compose.sh --profile radius
   run --rm --no-deps radius check`. UDP remains unpublished. Only PAP is enabled;
   CHAP, MSCHAP and EAP are rejected. Clients require Message-Authenticator.
4. Implement accounting packet behavior and the Disconnect outbox worker, then
   complete the milestone acceptance checks.

No Git commit or remote was present when work began. Local Git history is now
initialized; the policy-only main bootstrap is `e8b366b`. All repository content
remains local; no push or deployment was performed. The shell sandbox failed to
initialize; local reads and checks required escalated execution.
