# Deploying the foundation on Ubuntu Server LTS

This deploys the management service and SQL-backed FreeRADIUS PAP configuration. Run disposable packet tests before enabling NAS traffic. Accounting writes and Disconnect dispatch remain pending; keep the MikroTik configuration unchanged until those integrations are ready.

## Prepare the guest

Finish [Proxmox setup](proxmox-lab.md), enroll your SSH key and take the baseline snapshot. Use staging VM `103.215.107.181` for this initial deployment. Fetch source from GitHub, then select the reviewed commit that passed CI:

```sh
sudo apt-get update
sudo apt-get install -y git
sudo install -d -m 0755 -o "$(id -un)" -g "$(id -gn)" /srv/netloom
git clone --branch staging https://github.com/vsmann3/Netloom-Radius.git /srv/netloom/staging
cd /srv/netloom/staging
git switch --detach REVIEWED_FULL_COMMIT_SHA
```

Production is a separate VM at `103.215.107.180` and will fetch reviewed `main` releases only. Main currently contains policy files, not a deployable application; no production release is authorized before staging validation. See [environment separation](staging-production.md).

Review `scripts/prepare-linux.sh`, then run it on the fresh guest:

```sh
sudo sh scripts/prepare-linux.sh
```

The script supports Ubuntu 24.04/26.04 LTS and Debian 13, selecting the matching official Docker repository. It installs Git, Python and the QEMU guest agent as well. Docker host packages follow the stable channel; record their versions during validation. It does not change firewall policy or grant Docker-group privileges. The target is `radius.netnoc.in` on `103.215.107.180`; see [access and HTTPS status](deployment-target.md).

## Configure and start

Run from the repository as its owner:

```sh
cp deploy/staging.env.example .env
python3 scripts/init_secrets.py
sudo sh scripts/compose.sh config --quiet
sudo sh scripts/compose.sh build
sudo sh scripts/compose.sh up -d web
sudo sh scripts/compose.sh ps -a
sudo sh scripts/compose.sh exec web python manage.py check
sudo sh scripts/compose.sh exec web python manage.py createsuperuser
sudo sh scripts/compose.sh exec web python manage.py seed_lab --owner YOUR_USERNAME
```

`migrate` is a one-shot dependency, so web starts only after the database is healthy and migrations succeed. There is no automatic seed or destructive upgrade routine. To create test records explicitly:

```sh
sudo sh scripts/compose.sh exec web python manage.py seed_lab --synthetic-subscribers 500 --allow-synthetic-data
```

Synthetic subscribers have unusable passwords. This does not generate live PPPoE sessions or constitute a load test.

The wrapper loads both `image-lock.env` and `.env`; a plain `docker compose up` does not load the image lock. Secrets live under the owner-only `secrets/` directory, outside Git. On Linux individual files are read-only and readable through their container mounts by the non-root application user. Keep the parent directory mode `0700`; back it up separately in protected storage. Re-running secret initialization preserves existing credentials.

Only web publishes a port, on guest loopback. The database has no LAN listener. Staging uses port 8001. For initial SSH-tunnel access, temporarily set `DJANGO_SECURE_COOKIES=false` in the staging `.env`; restore it to `true` before HTTPS network access:

```sh
ssh -L 8001:127.0.0.1:8001 YOUR_USERNAME@103.215.107.181
```

Open `http://127.0.0.1:8001/` locally. Before network browser access, configure an HTTPS reverse proxy, allowed hosts and trusted CSRF origins, set `DJANGO_SECURE_COOKIES=true`, and verify the management-network firewall. No proxy is included yet; Django does not trust forwarded headers by default. Staging DNS must point to `.181`; production `radius.netnoc.in` stays on `.180`.

## Checks on the VM

Run the isolated SQL/PAP packet harness first:

```sh
sudo python3 scripts/test_radius.py
```

The harness generates credentials, creates a new random project and volume, runs SQL/PAP checks plus the Django tests against MariaDB, then removes that project's resources. It publishes no host ports. A failure means NAS traffic must remain unpublished. See [test coverage](development.md).

After the normal lab migrations complete, validate its FreeRADIUS configuration:

The entrypoint loads the restricted SQL secret and performs `freeradius -XC` before serving requests. The `check` argument validates and exits:

```sh
sudo sh scripts/compose.sh --profile radius run --rm --no-deps radius check
```

Use the one-shot form for validation. Record the result; this has not been run on the Windows development host.

Verify `curl -f http://127.0.0.1:8001/health/` on staging, restart services and check that tenant records persist. From an unauthorized LAN host verify database port 3306 and panel loopback ports are inaccessible. UDP 1812/1813 remain unpublished until integration validation and the NAS allowlist are ready. Check Proxmox, guest and Docker firewall behavior separately.

## Database roles and existing volumes

Fresh volumes run `deploy/db/10-service-users.sh` automatically. Runtime has no CREATE/DROP privileges; migrations use `netloom_migrate`. FreeRADIUS can read only the authorization view and has no accounting/write grant.

For a volume created before those roles were introduced, initialize the additional secret files and apply the grants before migrations:

```sh
python3 scripts/init_secrets.py
sudo sh scripts/compose.sh up -d db
# Wait for db to become healthy, then:
sudo sh scripts/compose.sh exec -T db sh /docker-entrypoint-initdb.d/10-service-users.sh
sudo sh scripts/compose.sh run --rm migrate
```

The script preserves data and sets service passwords to the secret files. Changing secrets requires coordinating grants and restarting affected services. Keep `netloom_migrate`: it is the authorization view's definer.

## Provisioning PAP passwords and NAS clients

Set an existing subscriber's PAP password through a hidden prompt, with an explicit tenant and tenant owner/operator actor:

```sh
sudo sh scripts/compose.sh exec web python manage.py set_subscriber_password --tenant lab --username SUBSCRIBER --actor YOUR_USERNAME
```

The change is audited. This does not create or activate a subscriber. CHAP/MSCHAP are disabled. NAS/subscriber creation currently uses trusted operator tooling; an ISP-facing editor is pending.

For registered NAS records, place each unique 64-character lowercase hex shared secret at `secrets/nas/SECRET_REF`, with the directory owner-only. Generate secrets directly into files, never command-line arguments or Git. Render using a temporary operator container with explicit secret/output mounts:

```sh
mkdir -m 0700 -p .radius-config
sudo sh scripts/compose.sh run --rm --no-deps --user "$(id -u):$(id -g)" \
  -v "$PWD/secrets/nas:/operator/nas:ro" -v "$PWD/.radius-config:/operator/output" \
  web python manage.py render_radius_clients --secret-dir /operator/nas --output /operator/output/clients.conf
install -m 0444 .radius-config/clients.conf secrets/radius_clients
sudo sh scripts/compose.sh --profile radius run --rm --no-deps radius check
sudo sh scripts/compose.sh --profile radius up -d --force-recreate radius
```

The normal web service has no NAS-secret or writable RADIUS-config mount. Review client source addresses before the install step. The renderer blocks path traversal and requires Message-Authenticator; verify the target RouterOS version/configuration supports it. Disabled NAS records immediately fail SQL authorization; additions and secret rotations need a validated recreation of the RADIUS container.

## Upgrade, backup and restore

Before an upgrade, create an application dump and preserve the previous Git revision and image lock:

```sh
sudo sh scripts/backup.sh
```

Quiesce schema migrations during a dump. The backup uses a consistent InnoDB snapshot and includes triggers. A failed dump retains a `.partial` file and is never labelled successful. Copy completed compressed dumps off the VM; secrets are separate. Never commit either to Git.

For an upgrade, stop web, build the reviewed revision, run `migrate` explicitly, then start web:

```sh
sudo sh scripts/compose.sh stop web
sudo sh scripts/compose.sh build
sudo sh scripts/compose.sh run --rm migrate
sudo sh scripts/compose.sh up -d web
```

For a restore drill use a **separate clean lab installation**, initialize its secrets, start only `db`, and import a decompressed copy of the dump:

```sh
gzip -dk backups/YOUR_BACKUP.sql.gz
sudo sh scripts/compose.sh up -d db
# Wait for db to report healthy before the import.
sudo sh scripts/compose.sh exec -T db sh -ec 'export MYSQL_PWD="$(cat /run/secrets/db_root_password)"; exec mariadb -uroot netloom' < backups/YOUR_BACKUP.sql
sudo sh scripts/compose.sh up -d web
```

Check migrations, membership, subscriber counts and suspension records. Dump/import and rollback have not yet been executed. Do not use `down -v` on an installation containing data. Code rollback across schema changes requires a reviewed reverse migration or restoring into a separate instance from the matching backup; do not assume an older image alone is enough.
