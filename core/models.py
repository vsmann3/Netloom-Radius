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
    # Populated only by a future audited renewal workflow; never infer from expiry.
    last_renewed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "expires_at"], name="subscriber_tenant_expiry"),
            models.Index(fields=["tenant", "created_at"], name="subscriber_tenant_created"),
            models.Index(fields=["tenant", "last_renewed_at"], name="subscriber_tenant_renewed"),
        ]
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


class CAFCompanyBinding(models.Model):
    """Explicitly reviewed external binding; never resolve a company by name."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.SlugField(max_length=64)
    caf_company_id = models.CharField(max_length=128)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "caf_company_id"], name="caf_source_company_unique"),
            models.UniqueConstraint(fields=["source", "tenant"], name="caf_source_tenant_unique"),
        ]


class CAFServiceToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    binding = models.ForeignKey(CAFCompanyBinding, on_delete=models.PROTECT)
    # High-entropy random bearer secret; only its SHA-256 digest is stored.
    secret_digest = models.CharField(max_length=64, editable=False)
    plans_read = models.BooleanField(default=False)
    reservations_write = models.BooleanField(default=False)
    provisionings_write = models.BooleanField(default=False)
    receipts_read = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    rate_window = models.PositiveBigIntegerField(default=0, editable=False)
    rate_count = models.PositiveIntegerField(default=0, editable=False)


class CAFPlanPublication(models.Model):
    """Versioned, explicitly published snapshot; legacy plans have no validity."""

    plan = models.OneToOneField(Plan, on_delete=models.PROTECT, primary_key=True)
    version = models.PositiveBigIntegerField(default=1)
    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100)
    upload_kbps = models.PositiveIntegerField()
    download_kbps = models.PositiveIntegerField()
    duration_seconds = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(version__gte=1) & Q(version__lte=9007199254740991), name="caf_plan_version_range"),
            models.CheckConstraint(condition=Q(duration_seconds__gte=1), name="caf_plan_positive_duration"),
            models.CheckConstraint(condition=Q(upload_kbps__gte=1) & Q(download_kbps__gte=1), name="caf_plan_positive_rates"),
        ]


class CAFFranchiseBinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(CAFCompanyBinding, on_delete=models.PROTECT)
    caf_franchise_id = models.CharField(max_length=128)
    franchise_id = models.PositiveBigIntegerField(unique=True, default=next_organization_number, editable=False)
    name = models.CharField(max_length=160)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "caf_franchise_id"], name="caf_franchise_mapping_unique")]


class CAFCustomerLink(TenantRecord):
    source = models.SlugField(max_length=64)
    binding = models.ForeignKey(CAFCompanyBinding, on_delete=models.PROTECT)
    franchise = models.ForeignKey(CAFFranchiseBinding, on_delete=models.PROTECT)
    customer_id = models.CharField(max_length=10, validators=[RegexValidator(r"\A[1-9][0-9]{9}\Z")])
    profile_version = models.PositiveBigIntegerField(default=0)
    profile = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "customer_id"], name="caf_lifetime_customer_unique")]


class CAFServiceRequest(TenantRecord):
    source = models.SlugField(max_length=64)
    binding = models.ForeignKey(CAFCompanyBinding, on_delete=models.PROTECT)
    franchise = models.ForeignKey(CAFFranchiseBinding, on_delete=models.PROTECT)
    service_request_id = models.UUIDField()
    customer_id = models.CharField(max_length=10)
    username = models.CharField(max_length=64)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    plan_version = models.PositiveBigIntegerField()
    customer_link = models.ForeignKey(CAFCustomerLink, on_delete=models.PROTECT, null=True)
    subscriber = models.OneToOneField(Subscriber, on_delete=models.PROTECT, null=True, related_name="caf_request")
    credential_accepted = models.BooleanField(default=False)
    state = models.CharField(max_length=32, default="reserved")
    approval_event_id = models.UUIDField(null=True)
    activated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "service_request_id"], name="caf_service_request_unique")]


class CAFUsernameClaim(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    normalized_username = models.CharField(max_length=64)
    request = models.OneToOneField(CAFServiceRequest, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "normalized_username"], name="caf_username_claim_unique")]


class CAFReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(CAFServiceRequest, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()


class CAFDeliveryReceipt(TenantRecord):
    source = models.SlugField(max_length=64)
    binding = models.ForeignKey(CAFCompanyBinding, on_delete=models.PROTECT)
    operation = models.CharField(max_length=32)
    delivery_id = models.UUIDField()
    request = models.ForeignKey(CAFServiceRequest, on_delete=models.PROTECT, null=True)
    fingerprint = models.CharField(max_length=64)
    binding_fingerprint = models.CharField(max_length=64, blank=True)
    key_id = models.CharField(max_length=64)
    response = models.JSONField(default=dict)
    http_status = models.PositiveIntegerField(default=202)
    predecessor = models.OneToOneField("self", on_delete=models.PROTECT, null=True, related_name="successor")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "operation", "delivery_id"], name="caf_delivery_once")]
