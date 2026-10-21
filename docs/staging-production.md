# Staging and production

Follow [the release policy](../RELEASE_POLICY.md): local checks, GitHub CI,
deployed staging validation, `staging` → `main` pull request, then production.
The VM fetches code from GitHub; local file copying is not the deployment source.

## Initial topology

| Setting | Staging | Production |
| --- | --- | --- |
| Git branch | `staging` | `main` |
| Checkout | `/srv/netloom/staging` | `/srv/netloom/production` |
| Compose project | `netloom-radius-staging` | `netloom-radius-production` |
| Web loopback port | `8001` | `8000` |
| Hostname | `staging-radius.netnoc.in` proposed | `radius.netnoc.in` |
| Configuration template | `deploy/staging.env.example` | `deploy/panel.env.example` |
| Database, volumes and secrets | Staging-only | Production-only |

The user supplied VM address `103.215.107.180`. The staging hostname still needs
confirmation/DNS; HTTPS and SSH setup remain pending. No environment is deployed
yet. If both environments share this VM, Compose project names isolate their
networks and volumes, but host availability/resources are shared.

Each checkout has its own ignored `.env` and `secrets/` directory. Never symlink
or copy production secrets/data into staging. Generate staging credentials
independently and use synthetic subscribers plus a test NAS. Do not register the
same real NAS source/secret for testing against both environments.

## Fetching a release

Use a repository read-only deploy key on the VM. Once the repository URL is
confirmed, clone it into the appropriate environment directory. Before deployment,
fetch the relevant branch and select the reviewed full commit SHA:

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
each checkout. The Compose project name and image tag must differ so staging
commands cannot select production's containers, volume or image tag. The web
service remains on loopback behind the HTTPS proxy.

## Gates

GitHub Actions runs application checks and a disposable MariaDB/FreeRADIUS packet
test on pushes and pull requests involving `staging`/`main`. A production PR must
come from this repository's `staging` branch. Branch protection should require
these checks and a pull request, with force pushes and branch deletion disabled.
Actual server-side enforcement depends on repository permissions and GitHub plan;
do not call it enforced until its API/settings have been verified.

After CI passes, deploy the staging SHA and test the website, migrations,
subscriber isolation and test NAS behavior. Only then promote via a pull request.
There is no automatic production deploy in this repository. Environment-specific
SSH/deployment automation can be configured once VM access is established.
