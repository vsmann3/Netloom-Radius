# Resume here - saved 2026-10-21

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
