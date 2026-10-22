# Resume here - saved 2026-10-21

## Latest confirmed direction - 2026-10-22

User confirmed the Tabler dashboard works on the VM. User then requested mandatory
numeric company/franchise IDs of at least five digits and shorter company URLs.
Implemented company_id and migration 0004 with backfill, numeric browser routes,
authorized UUID redirects and visible IDs. Internal UUIDs and tenant API stay intact.
Local suite: 44 tests, 38 passed, 6 MariaDB-only skipped. This increment requires
a real migration before web recreation; do not reuse the no-migration dashboard
deployment command. See company-numbers.md. Franchise numbering is mandatory when
the franchise model is built; franchise features are not implemented yet.

The user requested a prebuilt dashboard instead of the basic pages. A Tabler 1.6.1
UI is implemented with local vendored CSS, responsive templates, company switching,
scoped counts and WhiteNoise 6.12.0 static serving. Local 40-test suite passed
(5 MariaDB-only skips); desktop/mobile browser workflows and screenshots checked.
No migration. See dashboard-ui.md. VM deployment still needs console sudo; do not
claim the UI is live until its deployment and external static response are verified.

Live company onboarding completed successfully (user supplied console output).
Existing panel account `suradmin` received explicit owner memberships for
Infolink Broadband (`infolink-broadband`), NorthNet (`northnet`) and VM Net (`vm-net`).
No credentials changed. Pre-onboarding backup:
backups/netloom-20261022T021421Z.sql.gz. Off-VM backup/restore remain unverified.
Source and rebuilt image are fdc3f7c; onboarding ran in disposable web command
containers. The running web service was not recreated during this onboarding;
its c394450 company page reads the new memberships directly from the database.
CI passed: https://github.com/vsmann3/Netloom-Radius/actions/runs/39709912123.
Dashboard visibility is awaiting the user's refresh; do not rerun onboarding
or reset the account simply to check visibility.

Company names confirmed: Infolink Broadband, NorthNet and VM Net. Proposed tenant
slugs are in product-direction.md. Pilot choice and owner memberships remain pending;
no live company records have been created from these names yet.

Management revision c394450 passed all GitHub checks, including MariaDB/FreeRADIUS:
https://github.com/vsmann3/Netloom-Radius/actions/runs/39706076821.
A deployment helper is staged at /home/jarvis/netloom-deploy-management-c394450.sh
on the VM. The user confirmed successful deployment of c394450, Django checks and
health status ok. Pre-update backup: backups/netloom-20261022T013641Z.sql.gz;
off-VM backup and restore are still unverified.

The user authorized onboarding all three companies with their existing panel
account. A new onboard_companies command supports preview then explicit --apply,
atomic audited creation and idempotent owner membership grants. Do not assume the
panel username is jarvis. SSH sudo remains password-protected, so live inspection
and onboarding require console execution. See company-onboarding.md.

The user confirmed proceeding with Django for their own three companies first,
with multiple franchises and full wallet/recharge/commission/revenue-sharing needs.
Later offer the proven software to fellow ISPs. See [product direction](product-direction.md).
This supersedes the reuse-first pause below. A local company-management increment
adds scoped plan/subscriber creation, paginated listing, suspension and owner-only
disabled NAS registration; new subscriber credentials remain disabled until
provisioned. Local suite: 26 passed, 5 MariaDB-only skipped; no migration needed.
Deployment and live membership checks remain pending;
SSH works but Docker access requires administrative access.

## Superseding direction - 2026-10-22

The user chose reuse of established software over building a new custom product.
Pause new Django management features. Evaluate daloRADIUS, allow separate ISP
installations, and require demonstrated multiple-franchise support before selection.
See [reuse-first direction](reuse-first.md) for findings and acceptance requirements.
Existing deployment remains intact. The user confirmed mandatory franchise wallets,
recharge balances, commissions and revenue sharing. Evaluate existing platforms
against these requirements. The older custom-panel next steps below are superseded.

The user ended today's session and confirmed successful login at
https://radius.netnoc.in. Resume from this checkpoint tomorrow. This is a project
conversation summary, not a verbatim export of the chat. No credentials are stored here.

## Current decisions

- Use upstream FreeRADIUS 3.2.10 unchanged as the AAA engine, MariaDB and a custom
  Django panel. Ubuntu is the selected VM OS.
- Public source: https://github.com/vsmann3/Netloom-Radius. Maintained code, tests,
  migrations and configuration templates go to GitHub; VM fetches source there.
- Initial development and testing now use main on 103.215.107.180. This supersedes
  the earlier staging-first plan. Once initial functionality is accepted, protect
  main and activate staging on the separate 103.215.107.181 VM for future work.
- Main currently permits direct development pushes; force push/deletion remain
  disabled. Existing staging branch is retained but is not the active source.

## Live environment

- URL https://radius.netnoc.in; public DNS resolves to 103.215.107.180.
- SSH jarvis, port 22; dedicated local key ~/.ssh/netloom_radius_ed25519, outside Git.
- Console-verified host fingerprint:
  SHA256:4Q+IkESOmiCXqfGEFk4fNbom7JdFpCONF6nXxw8feLc.
- Ubuntu 24.04.4 LTS, about 4 GB RAM, 95 GB root disk. Docker 29.9.2,
  Compose 5.6.1 and QEMU guest agent installed.
- Checkout /srv/netloom/production, branch main; environment and secrets ignored.
- Django and MariaDB healthy; migrations completed; FreeRADIUS runs internally.
- Nginx proxies public HTTPS to 127.0.0.1:8000. Database and RADIUS ports are not
  published. No real NAS was changed or enabled.
- Let's Encrypt certificate expires 2027-01-19. HTTP redirects to HTTPS.
  Certbot timer and Nginx reload hook installed; renewal dry-run succeeded.
- User confirmed panel login works. Do not recreate/reset their account or assume
  their chosen panel username matches the SSH username. Tenant membership should
  be checked before onboarding an ISP.
- Temporary /etc/sudoers.d/90-netloom-bootstrap rule was removed; normal sudo needs
  the user's password. Never ask for a password in chat. If administrative work is
  needed, prepare concrete changes and arrange console execution/access as needed.

## Verified today

- Full disposable FreeRADIUS/MariaDB packet integration suite passed on the VM:
  PAP, rate attributes, tenant isolation, rejection cases, NAS spoofing, unsupported
  methods, unknown clients, restricted grants, suspension and DB outage rejection.
- All 21 Django tests passed against MariaDB; synthetic packets are not PPPoE tests.
- Health endpoint, login GET, secure CSRF cookie, CSRF-valid invalid-login POST,
  TLS 1.3 and HTTP redirect verified externally. User then logged in successfully.
- Services survived a restart. Initial DB dump gzip integrity passed; restore and
  off-VM backup are still pending. No claim of a verified restore.
- HTTPS code CI passed:
  https://github.com/vsmann3/Netloom-Radius/actions/runs/39646309389.
- Source changes include a separate web frontend network for Docker loopback
  publishing, Gunicorn control socket disabled on read-only filesystem, and
  scripts/setup-https.sh plus deploy/nginx configuration.

## Next work

1. Review the actual logged-in panel with the user and confirm ISP/tenant membership
   and the first management workflows. Current UI is a minimal foundation.
2. Implement tenant-scoped subscriber, plan and NAS management as needed; keep NAS
   shared secrets outside the normal web container and Git.
3. Implement accounting writes and the Disconnect outbox dispatcher; both remain
   pending. Do not enable real MikroTik traffic before those acceptance checks.
4. Obtain test NAS source address and RouterOS version; validate PAP and required
   Message-Authenticator compatibility, real PPPoE rate enforcement and Disconnect.
5. Complete restore/off-VM backup and load/unauthorized-network checks before live
   acceptance. After acceptance, activate protected-main plus separate staging flow.

## Local tools and references

Windows workspace E:/Netloom/Netloom-Radius. Git needs
-c safe.directory=E:/Netloom/Netloom-Radius in this environment. Local .venv exists.
No local Docker/WSL; integration runs on GitHub Ubuntu CI or the VM.
GitHub CLI is authenticated as vsmann3. For source pushes, ignored helper
.dependency-check/push_github.py uses a temporary repository-only write key and
revokes it immediately. Never reuse the unrelated infolink SSH key.
See RELEASE_POLICY.md, docs/vm-checkpoint.md, docs/architecture.md and
 docs/milestone-1.md for further context. Earlier staging-first and undeployed/DNS
pending wording in other historical docs is superseded by this checkpoint.
