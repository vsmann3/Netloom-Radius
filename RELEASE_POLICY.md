# Source control and release policy

Maintained source, templates, migrations, tests and dependency locks belong in
https://github.com/vsmann3/Netloom-Radius. Secrets, private keys, customer data,
dumps and generated runtimes stay outside Git.

## Initial build phase (user decision, 2026-10-21)

Develop and validate the initial system on `main`, then deploy exact CI-passing
commits fetched from GitHub to `/srv/netloom/production` on `103.215.107.180`.
This is initial development, not an accepted production release. Real NAS traffic
must wait for authentication, accounting and Disconnect acceptance.
Main PR/status enforcement is deferred until the initial system is ready;
force pushes and branch deletion remain disabled. CI continues to run on main.
The existing staging branch is retained but is not the active development source.

## After initial acceptance

Protect main with required pull requests and application, integration and promotion
checks. Refresh staging from the accepted main baseline and deploy it separately
on `103.215.107.181`. Future changes go through local checks, CI, deployed staging
acceptance, a staging-to-main PR, then a reviewed production deployment.
No automatic production deployment is enabled.

The two VMs must use independent databases, volumes and credentials. Staging uses
synthetic data and a test NAS, never production secrets or subscriber data.
