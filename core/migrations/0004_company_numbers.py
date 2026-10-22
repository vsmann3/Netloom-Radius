import core.identifiers
from django.db import migrations, models


def assign_numbers(apps, schema_editor):
    Tenant = apps.get_model("core", "Tenant")
    Number = apps.get_model("core", "OrganizationNumber")
    alias = schema_editor.connection.alias
    for tenant in Tenant.objects.using(alias).order_by("id").iterator():
        number = Number.objects.using(alias).create()
        Tenant.objects.using(alias).filter(pk=tenant.pk).update(company_id=number.pk + 10000)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_radius_authorization")]
    operations = [
        migrations.CreateModel(name="OrganizationNumber", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("issued_at", models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.AddField(model_name="tenant", name="company_id",
                            field=models.PositiveBigIntegerField(null=True, editable=False, unique=True)),
        migrations.RunPython(assign_numbers, migrations.RunPython.noop),
        migrations.AlterField(model_name="tenant", name="company_id",
                              field=models.PositiveBigIntegerField(default=core.identifiers.next_organization_number, editable=False, unique=True)),
        migrations.AddConstraint(model_name="tenant", constraint=models.CheckConstraint(
            condition=models.Q(company_id__gte=10000), name="company_id_min_five_digits")),
    ]
