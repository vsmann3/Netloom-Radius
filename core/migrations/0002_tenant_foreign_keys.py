"""Enforce tenant ownership even for writes bypassing Django validation.

MariaDB gets composite foreign keys. SQLite uses equivalent ownership triggers
for local tests because SQLite cannot ALTER TABLE to add composite foreign keys.
"""
from django.db import migrations

LINKS = [
    ("core_subscriber", "plan_id", "core_plan", "subscriber_plan_tenant_fk"),
    ("core_session", "nas_id", "core_nas", "session_nas_tenant_fk"),
    ("core_session", "subscriber_id", "core_subscriber", "session_subscriber_tenant_fk"),
    ("core_routeraction", "session_id", "core_session", "action_session_tenant_fk"),
]


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    for child, column, parent, name in LINKS:
        if vendor == "mysql":
            schema_editor.execute(
                f"ALTER TABLE {child} ADD CONSTRAINT {name} FOREIGN KEY ({column}, tenant_id) "
                f"REFERENCES {parent} (id, tenant_id) ON DELETE RESTRICT ON UPDATE RESTRICT"
            )
        elif vendor == "sqlite":
            for operation in ("INSERT", "UPDATE"):
                schema_editor.execute(
                    f"CREATE TRIGGER {name}_{operation.lower()} BEFORE {operation} ON {child} "
                    f"WHEN NOT EXISTS (SELECT 1 FROM {parent} WHERE id = NEW.{column} AND tenant_id = NEW.tenant_id) "
                    "BEGIN SELECT RAISE(ABORT, 'tenant ownership mismatch'); END"
                )
            schema_editor.execute(
                f"CREATE TRIGGER {name}_parent BEFORE UPDATE OF id, tenant_id ON {parent} "
                f"WHEN EXISTS (SELECT 1 FROM {child} WHERE {column} = OLD.id "
                "AND (tenant_id != NEW.tenant_id OR NEW.id != OLD.id)) "
                "BEGIN SELECT RAISE(ABORT, 'tenant ownership mismatch'); END"
            )
        else:
            raise RuntimeError("Only MariaDB and SQLite test databases are supported")


def uninstall(apps, schema_editor):
    for child, column, parent, name in reversed(LINKS):
        if schema_editor.connection.vendor == "mysql":
            schema_editor.execute(f"ALTER TABLE {child} DROP FOREIGN KEY {name}")
        elif schema_editor.connection.vendor == "sqlite":
            for suffix in ("insert", "update", "parent"):
                schema_editor.execute(f"DROP TRIGGER {name}_{suffix}")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
