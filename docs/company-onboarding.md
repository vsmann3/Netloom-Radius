# Company onboarding

Confirmed companies: Infolink Broadband, NorthNet and VM Net. Each gets an
independent tenant and explicit owner membership for the user's existing panel
administrator. Existing lab data is preserved; no routers, plans, subscribers or
franchise balances are invented or copied.

Use the existing active panel superuser's exact username, which may differ from
the SSH username. The management command never creates users or changes passwords.
It requires an active platform administrator and stops on inactive tenants,
conflicting names or existing non-owner memberships instead of overwriting them.

With the tested application image available, preview:

```sh
sudo sh scripts/compose.sh run --rm --no-deps web python manage.py onboard_companies \
  --owner YOUR_PANEL_USERNAME \
  --company 'infolink-broadband=Infolink Broadband' \
  --company 'northnet=NorthNet' \
  --company 'vm-net=VM Net'
```

Repeat with `--apply` to commit. All companies, memberships and their audit records
commit together. Repeating an applied command creates no duplicate records/audits.
The web dashboard immediately reads new memberships from the shared database;
no logout or password reset is required.

This provisions company access only. Pilot choice, actual franchise details,
commercial split rules and live NAS acceptance remain separate steps.
