# Dashboard UI

The management interface uses the MIT-licensed Tabler 1.6.1 dashboard stylesheet
with Django templates. Vendor CSS and its license are in core/static/vendor/tabler;
Netloom layout rules are in core/static/netloom/app.css. No browser CDN requests,
Node build or frontend framework are required. Native links/details controls handle
navigation and company switching. A small local compatibility script redirects
old company section bookmarks to the new dedicated pages.

WhiteNoise 6.12.0 serves collected local assets with DEBUG disabled. The Docker
image collects assets at build time using placeholder settings, without connecting
to the database. No deployment credentials are used during static collection.

## Pages and behavior

- Responsive login, company overview and company management pages.
- Sidebar navigation, authorized company switcher and POST-only sign out.
- Real tenant-scoped summary counts, tables, status badges, form labels/errors and
  pagination. Active subscriptions means active/unexpired records, not live sessions.
- Existing plan/subscriber creation, owner-only disabled NAS registration and
  suspension authorization/CSRF/audit behavior are preserved.
- Franchise/wallet navigation is explicitly marked planned; it has no fake actions
  or financial totals.

## Validation

Local suite: 40 tests, 35 passed and 5 MariaDB-only skipped. Static CSS responses
are tested without DEBUG or a database; scoped count tests prevent cross-company
summary leakage. No model migration needed.

Headless Chrome against a disposable SQLite fixture verified login, plan/subscriber
creation, suspension, company switching, company isolation, logout, unique form IDs,
local CSS loading and no external requests. Desktop (1440px) and mobile (390px)
screenshots were inspected; mobile pages had no document-level horizontal overflow.
Fixtures and preview screenshots are ignored local artifacts, not live company data.

References:
- https://docs.tabler.io/ui/getting-started
- https://github.com/tabler/tabler/releases/tag/%40tabler%2Fcore%401.6.1
- https://whitenoise.readthedocs.io/en/stable/django.html
