"""A narrow SQL interface to upstream rlm_sql / rlm_pap; no username rewrite."""
from django.db import migrations

# SQL SECURITY DEFINER permits SELECT without granting access to base tables.
# [$] avoids backslash escaping differences between SQL modes.
CREATE_VIEW = """
CREATE OR REPLACE SQL SECURITY DEFINER VIEW radius_authorization AS
SELECT s.id AS subscriber_id, s.tenant_id, n.source_ip,
       s.username,
       CONCAT('$PBKDF2$HMACSHA2+256:',
           SUBSTRING_INDEX(SUBSTRING_INDEX(s.password_hash, '$', 2), '$', -1), ':',
           TO_BASE64(SUBSTRING_INDEX(SUBSTRING_INDEX(s.password_hash, '$', 3), '$', -1)), '$',
           SUBSTRING_INDEX(s.password_hash, '$', -1)) AS pap_password,
       CONCAT(p.upload_kbps, 'k/', p.download_kbps, 'k') AS rate_limit,
       LEAST(2147483647, GREATEST(1, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), s.expires_at))) AS session_timeout
FROM core_subscriber s
JOIN core_tenant t ON t.id = s.tenant_id
JOIN core_nas n ON n.tenant_id = s.tenant_id
JOIN core_plan p ON p.id = s.plan_id AND p.tenant_id = s.tenant_id
WHERE t.active = 1 AND n.enabled = 1 AND s.status = 'active'
  AND s.expires_at > UTC_TIMESTAMP()
  AND BINARY s.password_hash REGEXP '^pbkdf2_sha256[$][1-9][0-9]{4,6}[$][A-Za-z0-9]{1,32}[$][A-Za-z0-9+/]{43}=$'
  AND CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(s.password_hash, '$', 2), '$', -1) AS UNSIGNED) BETWEEN 100000 AND 2000000
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute(CREATE_VIEW)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute("DROP VIEW IF EXISTS radius_authorization")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("core", "0002_tenant_foreign_keys")]
    operations = [migrations.RunPython(install, uninstall)]
