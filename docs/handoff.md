# Current checkpoint ? 2026-10-21

User superseded the staging-first workflow: initial build and VM testing use
main on 103.215.107.180; protect main and activate separate staging after initial
acceptance. SSH as jarvis works with a dedicated key, verified host fingerprint,
Ubuntu 24.04.4, 3.8 GiB RAM, 84 GiB free disk. Sudo needs a password, temporary
provisioning access requested. No application installed on the VM yet.
Read RELEASE_POLICY.md for the current policy. Historical notes below describe
the earlier staging-first approach and are superseded where they conflict.

---

# Work checkpoint

Updated 2026-10-21. The user selected Ubuntu for the Proxmox VM and supplied
`radius.netnoc.in` with VM/public SSH address `103.215.107.180`. SSH username/port,
key enrollment and the installed Ubuntu release are pending. Staging must use a
separate VM at `103.215.107.181`. The user authorized creating the public repository
`vsmann3/Netloom-Radius`; that repository has now been created. No remote VM deployment
has been performed. Details are in `docs/deployment-target.md`.

## Completed

- Built the first Django management/data foundation, migrations and tenant foreign keys.
- Added 21 application/SQL tests covering isolation, authorization, CSRF, password provisioning, client rendering, SQL policy/driver collations and outbox rollback.
- Added pinned Python dependencies and registry-resolved immutable image digests.
- Added Compose, Ubuntu/Debian preparation, secret initialization, backup and GitHub-to-staging deployment runbook.
- Replaced the baseline with upstream FreeRADIUS SQL/PAP configuration, a tenant-qualified authorization view and separate database accounts. Removed the temporary Python password verifier.
- Added audited hidden-prompt subscriber password provisioning and a NAS client renderer backed by external unique secrets.
- Added a disposable Compose/`radclient` packet harness; it publishes no host ports.

## Validation

Local Python 3.14 / Django 5.2.18: 16 SQLite tests pass, with five MariaDB-only
tests skipped. All 21 tests and the complete synthetic FreeRADIUS SQL/PAP packet
suite passed in Linux CI using the pinned containers. Evidence:
https://github.com/vsmann3/Netloom-Radius/actions/runs/39641740749 . It covers PAP
and plan attributes, same-name tenant isolation, rejection cases, NAS spoofing,
unsupported methods, unknown clients, privilege denials, suspension isolation
and database outage. These are synthetic RADIUS packets, not PPPoE sessions.

Initial portable MariaDB testing on Windows also passed; that test server was
stopped, with no Windows service installed. Download/test files remain ignored
under `.tools/` and `.dependency-check/`.

Django checks and migration consistency pass; both Compose YAML files parse and
port-exposure assertions pass. Production Python is pinned to 3.13.16. Neither
Docker nor WSL was installed on this Windows host. GitHub Ubuntu CI now performs
container and packet validation; actual staging/production VM deployment and
real MikroTik behavior remain pending.

## Resume here

The user requires all maintained source/templates/migrations/tests to be uploaded
to the public `vsmann3/Netloom-Radius` repository, with VM deployments fetched from GitHub.
Changes must pass CI and deployed staging validation before promotion from
`staging` to `main`. Local Git now has a policy-only `main` bootstrap and an
implementation `staging` branch. The CI workflow and separate staging/production
Compose project/image/port templates are prepared. Both branches are now published
to the public repository; main remains policy-only. Main protection requires a
PR plus Application checks, MariaDB and FreeRADIUS integration, and Promotion
policy, with administrator enforcement. Force push/deletion are disabled on both
branches. Publication used a temporary repository-only deploy key, revoked after
each push; no persistent GitHub SSH key was added.

The repository selection is resolved: the user explicitly requested a new public
`vsmann3/Netloom-Radius`. It was created via the authenticated GitHub CLI. Leave
the existing empty private `vsmann3/libre-radius` untouched.

The proposed staging hostname is `staging-radius.netnoc.in` on `103.215.107.181`;
the user has been asked to confirm/create its DNS. CI now runs on GitHub's Ubuntu
runner. CI exposed and verified fixes for reply-query collation, upstream PAP
header normalization and malformed unsupported-method test packets. The complete
suite now passes. Final integration configuration uses the normal VM startup
command, not diagnostic debug mode. Do not promote until the latest CI checks
and real staging VM validation pass. See `docs/staging-production.md`.

1. Obtain SSH username/port/key enrollment for both `.180` and `.181`, the installed
   Ubuntu release and MikroTik source IP/version. Follow `docs/lab-deployment.md`.
2. Run `sudo python3 scripts/test_radius.py` on Ubuntu. It exercises stock
   FreeRADIUS SQL/PAP with same-name subscribers in two tenants, rejection cases,
   NAS attribute spoofing, privilege denials and database outage; it cleans up
   only its randomly named disposable project. It passed on GitHub's Ubuntu
   runner; repeat on the actual staging VM before promotion.
3. Deploy the normal lab and validate `sudo sh scripts/compose.sh --profile radius
   run --rm --no-deps radius check`. UDP remains unpublished. Only PAP is enabled;
   CHAP, MSCHAP and EAP are rejected. Clients require Message-Authenticator.
4. Implement accounting packet behavior and the Disconnect outbox worker, then
   complete the milestone acceptance checks.

No Git commit or remote was present when work began. Local Git history is now
initialized; the policy-only main bootstrap is `e8b366b`. All repository content
is published on GitHub; neither VM has been deployed to. The shell sandbox failed
to initialize; local reads and checks required escalated execution.
