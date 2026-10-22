# Resume here - saved 2026-10-21

## Latest confirmed direction - 2026-10-22

Production-STAGED implementation is authorized; work now on staging, keeping main
at accepted/planning baseline5ff1bc9 pending owner review. New owner-only CAF
integration settings, encrypted reciprocal read key, one-time expiring four-grant
Radius keys, mappings/test/explicit enable, additive connection-status endpoint,
normal per-company write gate, trusted-proxy HTTPS, migration0011, Compose secret
overlay and preflight are implemented. See integrations/production-staged-settings.md.
Separate normal-gate HTTPS fixture18220->18150 is running; CA and private login
under ignored .tools/production-staged. CAF proxy18210->18160 awaits its own new
backend. Existing18110/18120 demo stays unchanged. Joint production-mode exchange,
MariaDB CI and owner acceptance remain pending. Do not infer activation authorization.


Owner now requests a working CAF/Radius model, not more contract-only exchanges.
Radius actual reservations, renewal, v2 provisioning/receipt, permanent customer
links and customer-ID directory/form handoff implemented at157edcb, with migration
and SQL-test fixes8fcc5e8/41f41f2/acd8e83 and canonical retry/password testse2a35c1.
CI39755317184 at e2a35c1 SUCCESS (application/MariaDB/stock SQL-PAP); prioracd8e83
CI also succeeds including real competing-delivery acceptance test. Latest local
suite85 total:78 pass7 SQL-specific skipped (new canonical case included).

Local Radius demo running127.0.0.1:18120; PID tracked in ignored
.tools/integration-demo/server.pid. Separate SQLite database; noNAS. Default STAGED
to match CAF worker; optional synthetic-active flag remains coordinated/demo-only.
Private access.txt and connection.json in same ignored folder (never print tokens).
Mapped sourcecaf-portal-demo, CAF companynetloom-demo-company/franchisenetloom-demo-franchise,
Radiuscompany10002, two published plans. Actual HTTP catalog and authenticated UI
smoke pass. Portable official PostgreSQL16.15 now running127.0.0.1:18130 with isolated
caf_demo_netloom DB; private caf-database.json passed to CAF peer via file reference.
CAF is now running at http://127.0.0.1:18110 with its actual form/client/worker.
Two real joint HTTP journeys PASS: a new customer and an additional connection
sharing lifetime Customer ID1000000000. Real plan proxy/reservation, approval scope,
automatic delivery, durable hash acceptance and retry without duplication/reset
verified. Both services remain STAGED/SUSPENDED; no internet activation.
Maintained reproduction: scripts/test_joint_caf_demo.py; private safe outcome in
.tools/integration-demo/joint-http-result.json. Owner checklist: working-demo.md.
Owner Vikas tested and accepted the isolated STAGED milestone and authorized
GitHub main promotion, as reported through the CAF coordination handoff. CAF
PR6/7/8 are merged; exact main d2a71e077d419a43f244fe7e068b5537710c41ab
independently confirmed with git ls-remote. Runtime implementation b9ad5b0;
CAF owner acceptance metadata1eee802. Radius implementation and demo evidence
already reside on main (157edcb through778b3b7). This acceptance applies only to
the demonstrated isolated STAGED journey. No production deployment, integration
enablement, activation policy or pending-KYC policy is authorized by this merge.
Further testable milestones still require owner testing and feedback.

Owner acceptance rule: after every testable milestone, ask Vikas to test with
environment, exact safe steps and expected results; await feedback before marking
accepted. Source/CI success is not deployment or owner acceptance.

Latest read-only deployment check: VM /srv/netloom/production HEAD is
1e57699715fbaff7253e46ca11f122b8084ad5f9 with clean git status. Public health returns
200/ok; login returns 200 with Tabler assets; users/plans/routers directory routes
redirect anonymous requests to login. The new CAF catalog endpoint returns 404.
Running-container/image revision could not be independently inspected because
sudo requires an interactive password. Do not equate checkout HEAD with verified
running-image SHA. Authenticated company data/UI were not inspected in this check.
Catalog source commits 8fadd0b/1feb9ee/e9d0e9b/5be76a6 and their CI success do not
establish deployment; no deployment or enabling was performed by this status check.

Owner resumed both developers after the coordination checkpoint. CAF was notified
directly. Reviewed CAF 36a5747 / Radius draft PR 1 and reran all 38 offline contract
tests successfully. PR 1 remains unmerged and activation policy unresolved.

First runtime integration slice: company-scoped hashed expiring service tokens,
immutable external bindings, explicit audited versioned plan publication with
fixed-duration validity, and the disabled-by-default HTTPS plan catalog endpoint.
See docs/integrations/caf-catalog-implementation.md. Migrations 0007–0009 add only
integration tables/triggers; no subscriber/AAA view changes. Local suite: 67 tests,
61 passed, 6 MariaDB-only skipped; migration drift/system/whitespace checks pass.
MariaDB/SQL/PAP CI and CAF peer runtime review are still required. Not deployed.
No customer/provisioning/activation endpoint is implemented by this slice.

User requested one self-contained handoff for the separate CAF Codex developer.
Canonical CAF-RADIUS-TEAM-HANDOFF.md at the repository root consolidates confirmed
decisions, both journeys, entity/field ownership, APIs/schemas, current gaps, the
single unresolved KYC-access question and a coordination/paste prompt. Use it as
the peer's starting point rather than asking the user to repeat the discussion.

User clarified approval scope: ONLY edits to basic customer/KYC information (such
as name/full name and CAF-required KYC fields) require CAF review. Radius is free
to manage credentials, plans, IP/network, billing and renewals under its own scoped
permissions/audit, syncing read-only metadata to CAF. Username/password changes
do NOT need CAF approval. Never mirror passwords/hashes/NAS secrets. CAF owns all
company/franchise/operator/customer onboarding. One question remains: retain last
approved access vs suspend an existing service while a later KYC revision awaits
review. Do not implement that unresolved access policy without confirmation.

Newest user proposal: CAF should own ALL organization/staff/customer onboarding;
Radius owns post-onboarding network/billing and publishes read-only summaries back
to CAF. Radius may request edits to CAF-owned data, but must submit revisions for
CAF-manager approval before applying them. Discussion captured in
docs/integrations/ownership-revisions-proposal.md. Open policies: keep existing
approved access vs suspend while a later revision is pending, and which technical/
billing changes need CAF approval. Do not implement the unresolved policy or claim
the expanded contract is confirmed yet. Earlier confirmed initial-approval gate
and permanent 10-digit customer ID remain valid.

User confirmed both onboarding journeys: company selection in CAF fetches Radius
plans; CAF assigns username, initial password and 10-digit customer/account ID;
CAF approval triggers initial activation (NO extra payment/wallet gate). Radius
validates/reserves usernames, accepts initial credentials securely and hashes them.
Add customer from Radius opens the same CAF form in a new tab with safe context/
return link; CAF owns self-service. Keep the SAME 10-digit ID for ALL customer ops.
Updated integration contract and dedicated sensitive provisioning schema reflect
this confirmation. Generic profile events remain credential-free. Endpoints are
still design artifacts, not implemented/enabled. Do not claim sync is working yet.

New boundary: user has another AI developer handling vsmann3/caf-portal. This agent
owns Radius/AAA and network operations; do not build a duplicate eCAF onboarding
form or document workflow. API-only integration. Use CAF's 10-digit customerId as
the main shared customer identifier; do not issue separate customer numbers here.
Company/franchise numbers remain distinct; subscriber UUID identifies a service.
CAF main reviewed at 05dbe819ff52a5fb022965a1113bd94981b2f167: customer ID sequence
exists, but Radius adapter is a no-op and payload omits customerId/version. A proposed
cross-developer contract, event schema and synthetic example are in docs/integrations/.
These are proposals, not live endpoints; no CAF code, credentials or runtime changed.

User requested separate pages for each management area and a filterable subscriber
directory. Implemented company overview plus /users/, /plans/ and /routers/ pages.
Subscriber filters cover account UUID, username, status, plan, validity, expiry,
creation and last recorded renewal dates, with sorting and persistent pagination.
0005 adds nullable last_renewed_at (no invented historical dates); 0006 adds date
lookup indexes. Renewal transactions remain pending. See directories.md.
Local 50-test suite passed (6 MariaDB-only skipped), desktop/mobile browser checks
passed. Numeric subscriber account IDs were asked about asynchronously; until
confirmed, account IDs remain UUIDs. Deployment needs the migration role before
recreating web; company-number and renewal/index migrations may all be pending on VM.

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
