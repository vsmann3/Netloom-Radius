# VM deployment checkpoint ? 2026-10-21

Initial development deployment: `103.215.107.180`, SSH `jarvis:22`, Ubuntu
24.04.4 LTS. Source fetched from public GitHub main into `/srv/netloom/production`.
Application revision: `3be3c81` (full SHA available through git rev-parse HEAD).
Docker Engine 29.9.2, Compose 5.6.1; QEMU guest agent active.

## Verified

- Dedicated SSH key login and console-confirmed host fingerprint.
- Disposable VM MariaDB/FreeRADIUS integration suite passed: PAP, plan attributes,
  same-name tenant isolation, rejection cases, source spoofing, unsupported methods,
  unknown clients, restricted grants, all Django MariaDB tests, suspension isolation,
  and database outage rejection. Synthetic packets, not PPPoE sessions.
- Persistent migrations completed, Django check passed, health endpoint returned ok.
- Normal FreeRADIUS configuration check passed.
- Initial database dump created and gzip integrity checked. Restore and off-VM copy
  are still pending; this is not a verified restore.
- Only web is published, on 127.0.0.1:8000. Database and RADIUS have no host ports.
- Web has a separate frontend network so Docker can publish its loopback port;
  database and RADIUS remain on the internal backend network.
- Gunicorn control socket disabled for read-only container filesystem.

## Pending

Public DNS for radius.netnoc.in returned NXDOMAIN from both the VM resolver and
Google public DNS at provisioning time. User asked to create/verify its A record
pointing to 103.215.107.180. HTTPS proxy/certificate not installed yet.
No management user or tenant has been created, and no real NAS has been changed.
Accounting writes and Disconnect dispatcher remain unimplemented.

After HTTPS is ready, create an operator through an interactive VM console:

```sh
cd /srv/netloom/production
sudo sh scripts/compose.sh exec web python manage.py createsuperuser
sudo sh scripts/compose.sh exec web python manage.py seed_lab --owner YOUR_USERNAME
```

This seeds a lab tenant, not live customer data. Temporary bootstrap sudo access
must be removed at the end of provisioning; future sudo uses the operator password.
The main/staging transition is described in RELEASE_POLICY.md.
