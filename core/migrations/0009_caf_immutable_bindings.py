"""Revocation is allowed; moving a token or external binding is never rotation."""
from django.db import migrations


RULES = [
    ("core_cafcompanybinding", "caf_binding_identity_fixed", ["source", "caf_company_id", "tenant_id"]),
    ("core_cafservicetoken", "caf_token_identity_fixed", ["binding_id", "secret_digest"]),
]


def install(apps, schema_editor):
    for table, name, columns in RULES:
        if schema_editor.connection.vendor == "mysql":
            changed = " OR ".join(f"NOT (BINARY NEW.{c} <=> BINARY OLD.{c})" for c in columns)
            schema_editor.execute(
                f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW "
                f"BEGIN IF {changed} THEN SIGNAL SQLSTATE '45000' "
                "SET MESSAGE_TEXT = 'CAF identity binding is immutable'; END IF; END"
            )
        elif schema_editor.connection.vendor == "sqlite":
            changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in columns)
            schema_editor.execute(
                f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} WHEN {changed} "
                "BEGIN SELECT RAISE(ABORT, 'CAF identity binding is immutable'); END"
            )
        else:
            raise RuntimeError("Only MariaDB and SQLite test databases are supported")


def uninstall(apps, schema_editor):
    for _, name, _ in reversed(RULES):
        schema_editor.execute(f"DROP TRIGGER {name}")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("core", "0008_cafservicetoken_rate_count_and_more")]
    operations = [migrations.RunPython(install, uninstall)]
