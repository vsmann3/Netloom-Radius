# Public company and franchise numbers

User decision: every company and future franchise needs a permanent numeric public
ID with at least five digits. New company numbers start at 10001 and can grow past
99999. They are assigned automatically and displayed in company cards/workspaces.

UUIDs remain internal primary/foreign keys. Company browser URLs use company_id,
for example `/companies/10001/#routers`. Changing a URL number never grants access;
membership checks still resolve against the internal tenant UUID. Existing UUID
company links redirect after authorization, preserving query strings. Existing UUID
POST routes continue to process already-open forms. UUID tenant API routes remain.

The OrganizationNumber table uses database auto-increment to issue numbers safely
under concurrent creation, with an offset of 10000. Retain registry rows; do not
reset the sequence or recycle identifiers. Gaps are acceptable. Future franchise
records must use the same allocator and enforce mandatory unique numbers; no
franchise model or wallet workflow is implemented by this change.

Migration 0004 backfills all existing tenants (including inactive/lab tenants), then
enforces NOT NULL, uniqueness and a minimum of 10000. It preserves UUIDs and existing
membership/subscriber/NAS relationships. Back up before migration; apply it with
the migration database account before starting the new web image.

Local checks: 44 tests, 38 passed, 6 MariaDB-only skipped. Tests cover numeric routes,
cross-company denial, UUID redirects, mandatory/unique IDs, stable IDs on rename and
an upgrade from the old schema with preserved memberships. The concurrent issuance
test runs on MariaDB in CI.
