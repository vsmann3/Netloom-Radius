# Staging and production

Follow [the release policy](../RELEASE_POLICY.md): local checks, GitHub CI,
deployed staging validation, `staging` → `main` pull request, then production.
The VM fetches code from GitHub; local file copying is not the deployment source.

## Initial topology

| Setting | Staging | Production |
| --- | --- | --- |
| Git branch | `staging` | `main` |
| VM address | `103.215.107.181` | `103.215.107.180` |
| Checkout | `/srv/netloom/staging` | `/srv/netloom/production` |
| Compose project | `netloom-radius-staging` | `netloom-radius-production` |
| Web loopback port | `8001` | `8000` |
| Hostname | `staging-radius.netnoc.in` proposed | `radius.netnoc.in` |
| Configuration template | `deploy/staging.env.example` | `deploy/panel.env.example` |
| Database, volumes and secrets | Staging-only | Production-only |

The user explicitly requires separate VMs. Staging uses `103.215.107.181` and
production uses `103.215.107.180`; never deploy both environments to either VM.
The proposed staging hostname needs DNS pointed at `.181`, not production's
`.180`. HTTPS, SSH enrollment and installed Ubuntu versions remain pending.
No environment is deployed yet.

Each checkout has its own ignored `.env` and `secrets/` directory. Never symlink
or copy production secrets/data into staging. Generate staging credentials
independently and use synthetic subscribers plus a test NAS. Do not register the
same real NAS source/secret for testing against both environments.

## Fetching a release

The public repository is `https://github.com/vsmann3/Netloom-Radius.git`. Public
HTTPS cloning needs no GitHub credential on the VM. Clone it into the appropriate
environment directory on its own VM. Before deployment, fetch the relevant branch
and select the reviewed full commit SHA:

```sh
git fetch origin
git switch --detach REVIEWED_FULL_COMMIT_SHA
git rev-parse HEAD
```

Verify that the staging SHA belongs to `origin/staging`, or the production SHA
belongs to `origin/main`. For example:

```sh
git merge-base --is-ancestor REVIEWED_FULL_COMMIT_SHA origin/staging
```

Use `origin/main` for production. Do not run `git pull` in a dirty checkout or
deploy an unreviewed moving branch tip. Record the deployed SHA with test results.
The release runbook's migration/build/start steps then apply within that checkout.

For initial staging configuration, copy `deploy/staging.env.example` to `.env`;
for production copy `deploy/panel.env.example`. Initialize secrets separately in
each checkout. Keep the environment-specific project names and image tags to
make the target clear. The separate VMs provide host and storage isolation; no
production mounts, database connections or secrets may be used on staging.
The web service remains on loopback behind the HTTPS proxy.

## Gates

GitHub Actions runs application checks and a disposable MariaDB/FreeRADIUS packet
test on pushes and pull requests involving `staging`/`main`. A production PR must
come from this repository's `staging` branch. Main branch protection is configured
and API-verified: pull requests and all three checks are required, the branch must
be up to date, administrator enforcement is enabled, and force pushes/deletion
are disabled. Staging also blocks force pushes and deletion. No separate reviewer
is required, so the repository owner can promote after recording staging acceptance.

After CI passes, deploy the staging SHA and test the website, migrations,
subscriber isolation and test NAS behavior. Only then promote via a pull request.
There is no automatic production deploy in this repository. Environment-specific
SSH/deployment automation can be configured once VM access is established.
