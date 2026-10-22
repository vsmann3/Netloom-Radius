import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from .identifiers import next_organization_number


class OrganizationNumber(models.Model):
    # Keep issued registry rows. Rollbacks may leave gaps; company and future
    # franchise numbers share this allocation namespace.
    id = models.BigAutoField(primary_key=True)
    issued_at = models.DateTimeField(auto_now_add=True)


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.PositiveBigIntegerField(unique=True, editable=False, default=next_organization_number)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=160)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(company_id__gte=10000), name="company_id_min_five_digits")]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        OPERATOR = "operator", "Operator"
        VIEWER = "viewer", "Viewer"

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=Role.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "user"], name="membership_tenant_user")]


class TenantRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Plan(TenantRecord):
    name = models.CharField(max_length=100)
    upload_kbps = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    download_kbps = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="plan_tenant_name"),
            models.UniqueConstraint(fields=["id", "tenant"], name="plan_id_tenant"),
            models.CheckConstraint(condition=Q(upload_kbps__gt=0) & Q(download_kbps__gt=0), name="plan_positive_rates"),
        ]


class Subscriber(TenantRecord):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    username = models.CharField(max_length=64, validators=[
        RegexValidator(r"\A[A-Za-z0-9_.@-]+\Z", "Use ASCII letters, digits, _, ., @ or -.")
    ])
    # PBKDF2-SHA256 is projected to stock FreeRADIUS PAP by the SQL view.
    # CHAP/MSCHAP require a separate credential-storage decision and are disabled.
    password_hash = models.CharField(max_length=128)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "username"], name="subscriber_tenant_username"),
            models.UniqueConstraint(fields=["id", "tenant"], name="subscriber_id_tenant"),
            models.CheckConstraint(condition=Q(status__in=["active", "suspended"]), name="subscriber_valid_status"),
        ]


class NAS(TenantRecord):
    name = models.CharField(max_length=100)
    source_ip = models.GenericIPAddressField(unique=True, protocol="IPv4")
    # An identifier for an external secret file; never the shared secret itself.
    secret_ref = models.SlugField(max_length=100)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["id", "tenant"], name="nas_id_tenant")]


class Session(TenantRecord):
    nas = models.ForeignKey(NAS, on_delete=models.PROTECT)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.PROTECT)
    session_id = models.CharField(max_length=128)
    # A trusted NAS boot epoch will be assigned by the accounting implementation.
    nas_epoch = models.UUIDField()
    started_at = models.DateTimeField()
    stopped_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField()
    input_octets = models.PositiveBigIntegerField(default=0)
    output_octets = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "nas", "nas_epoch", "session_id"], name="session_nas_epoch_identity"),
            models.UniqueConstraint(fields=["id", "tenant"], name="session_id_tenant"),
            models.CheckConstraint(condition=Q(stopped_at__isnull=True) | Q(stopped_at__gte=models.F("started_at")), name="session_stop_after_start"),
        ]


class RouterAction(TenantRecord):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    session = models.ForeignKey(Session, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, default="disconnect", editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    # A bounded machine-readable outcome, never raw router output or credentials.
    result_code = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind="disconnect"), name="router_action_disconnect_only"),
            models.CheckConstraint(condition=Q(state__in=["pending", "succeeded", "failed"]), name="router_action_valid_state"),
        ]


class AuditEvent(TenantRecord):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=64)
    target_id = models.UUIDField()
    outcome = models.CharField(max_length=32)
