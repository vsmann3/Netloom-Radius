from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from urllib.parse import urlencode, urlsplit

from .models import AuditEvent, Membership, NAS, Plan, Subscriber, Tenant
from .forms import NASForm, PlanForm, SubscriberForm, SubscriberFilterForm
from .directories import filter_subscribers
from .services import require_membership, suspend_subscriber
from .models import CAFCompanyBinding


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
@require_GET
def dashboard(request):
    memberships = Membership.objects.select_related("tenant").filter(user=request.user, tenant__active=True)
    tenant_ids = memberships.values_list("tenant_id", flat=True)
    return render(request, "dashboard.html", {
        "memberships": memberships,
        "subscriber_count": Subscriber.objects.filter(tenant_id__in=tenant_ids).count(),
        "plan_count": Plan.objects.filter(tenant_id__in=tenant_ids).count(),
        "nas_count": NAS.objects.filter(tenant_id__in=tenant_ids).count(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def company(request, company_id=None, tenant_id=None, section="overview"):
    tenant = get_object_or_404(Tenant, company_id=company_id) if company_id is not None else get_object_or_404(Tenant, pk=tenant_id)
    tenant_id = tenant.pk
    membership = require_membership(request.user, tenant_id, write=request.method == "POST")
    kind = request.POST.get("kind") if request.method == "POST" else None
    if kind == "subscriber" and getattr(settings, "CAF_FORM_URL", ""):
        return JsonResponse({"error": "Use the CAF onboarding form for new customers"}, status=409)
    plan_form = PlanForm(request.POST if kind == "plan" else None, tenant_id=tenant_id)
    subscriber_form = SubscriberForm(request.POST if kind == "subscriber" else None, tenant_id=tenant_id)
    nas_form = NASForm(request.POST if kind == "nas" else None)
    if request.method == "POST":
        if kind not in {"plan", "subscriber", "nas"}:
            return JsonResponse({"error": "Unknown action"}, status=400)
        if kind == "nas" and membership.role != Membership.Role.OWNER:
            raise PermissionDenied
        form = {"plan": plan_form, "subscriber": subscriber_form, "nas": nas_form}[kind]
        if form.is_valid():
            try:
                with transaction.atomic():
                    record = form.save(commit=False)
                    if kind == "nas":
                        record.tenant_id = tenant_id
                        record.enabled = False
                        record.secret_ref = f"nas-{record.id.hex}"
                    if kind == "subscriber":
                        record.password_hash = make_password(None)
                    record.save()
                    AuditEvent.objects.create(tenant_id=tenant_id, actor=request.user,
                                              action=f"{kind}.create", target_id=record.pk, outcome="saved")
            except IntegrityError:
                form.add_error(None, "The record conflicts with existing data. Check the details and try again.")
            else:
                return redirect({"overview": "company", "subscribers": "company-users", "plans": "company-plans", "routers": "company-routers"}[section], company_id=tenant.company_id)
    query = request.GET.copy()
    query.pop("page", None)
    filter_data = {"sort": "username", "per_page": "50", **query.dict()}
    filter_form = SubscriberFilterForm(filter_data, tenant_id=tenant_id)
    records = Subscriber.objects.filter(tenant_id=tenant_id).select_related("plan", "caf_request__customer_link")
    total_subscribers = records.count()
    if section == "subscribers":
        records = filter_subscribers(records, filter_form.cleaned_data) if filter_form.is_valid() else records.none()
    else:
        records = records.order_by("username", "id")
    per_page = (filter_form.cleaned_data.get("per_page") or 50) if section == "subscribers" else 100
    render_section = {"subscriber": "subscribers", "plan": "plans", "nas": "routers"}.get(kind, section) if section == "overview" else section
    advanced_fields = ["expiry_from", "expiry_to", "created_from", "created_to", "renewal_from", "renewal_to", "renewal_record"]
    return render(request, {"overview": "company.html", "subscribers": "users.html", "plans": "plans.html", "routers": "routers.html"}[render_section], {
        "section": render_section, "filter_form": filter_form, "filter_query": query.urlencode(),
        "caf_onboarding": bool(getattr(settings, "CAF_FORM_URL", "")),
        "integration_demo": getattr(settings, "CAF_DEMO_LOCAL_HTTP", False),
        "primary_filters": [filter_form[name] for name in ["account_id", "username", "status", "validity", "plan", "sort", "per_page"]],
        "advanced_filters": [filter_form[name] for name in advanced_fields],
        "advanced_open": any(filter_form[name].value() for name in advanced_fields),
        "total_subscribers": total_subscribers, "now": timezone.now(),
        "tenant": tenant, "can_write": membership.role in {"owner", "operator"},
        "membership": membership,
        "memberships": Membership.objects.select_related("tenant").filter(user=request.user, tenant__active=True),
        "subscriber_stats": Subscriber.objects.filter(tenant_id=tenant_id).aggregate(
            total=Count("id"), suspended=Count("id", filter=Q(status="suspended")),
            active=Count("id", filter=Q(status="active", expires_at__gt=timezone.now())),
        ),
        "can_manage_nas": membership.role == Membership.Role.OWNER,
        "devices": NAS.objects.filter(tenant_id=tenant_id).order_by("name"),
        "plans": Plan.objects.filter(tenant_id=tenant_id).order_by("name"),
        "records": Paginator(records, per_page).get_page(request.GET.get("page")),
        "plan_form": plan_form, "subscriber_form": subscriber_form, "nas_form": nas_form,
    })


@login_required
@require_GET
def caf_onboard(request, company_id):
    tenant = get_object_or_404(Tenant, company_id=company_id, active=True)
    require_membership(request.user, tenant.pk, write=True)
    base = getattr(settings, "CAF_FORM_URL", "")
    target = urlsplit(base)
    origin = f"{target.scheme}://{target.netloc}"
    allowed = getattr(settings, "CAF_FORM_ALLOWED_ORIGINS", [])
    if not base or origin not in allowed or target.query or target.fragment or target.username or target.password:
        return JsonResponse({"error": "CAF onboarding destination is not configured"}, status=503)
    if target.scheme != "https" and not (getattr(settings, "CAF_DEMO_LOCAL_HTTP", False) and target.hostname in {"127.0.0.1", "localhost"}):
        return JsonResponse({"error": "CAF requires a trusted HTTPS destination"}, status=503)
    binding = CAFCompanyBinding.objects.filter(tenant=tenant, active=True).first()
    if not binding:
        return JsonResponse({"error": "CAF company binding required"}, status=503)
    # Prefill only. CAF must enforce its own signed-in actor's company/franchise scope.
    return redirect(base + "?" + urlencode({"companyId": binding.caf_company_id,
        "returnTo": request.build_absolute_uri(reverse("company-users", args=[tenant.company_id]))}))


@login_required
@require_http_methods(["GET", "POST"])
def company_legacy(request, tenant_id):
    require_membership(request.user, tenant_id, write=request.method == "POST")
    if request.method == "POST":
        return company(request, tenant_id=tenant_id)
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    target = reverse("company", args=[tenant.company_id])
    if request.META.get("QUERY_STRING"):
        target += "?" + request.META["QUERY_STRING"]
    return redirect(target, permanent=True)


@login_required
@require_GET
def subscribers(request, tenant_id):
    require_membership(request.user, tenant_id)
    records = Subscriber.objects.filter(tenant_id=tenant_id).order_by("username").values(
        "id", "username", "status", "expires_at", "plan_id",
    )[:100]
    return JsonResponse({"subscribers": list(records), "limit": 100})


@login_required
@require_POST
def suspend(request, tenant_id, subscriber_id):
    subscriber, queued = suspend_subscriber(actor=request.user, tenant_id=tenant_id, subscriber_id=subscriber_id)
    return JsonResponse({"id": str(subscriber.id), "status": subscriber.status, "disconnects_queued": queued})


@login_required
@require_POST
def suspend_from_company(request, subscriber_id, company_id=None, tenant_id=None):
    tenant = get_object_or_404(Tenant, company_id=company_id) if company_id is not None else get_object_or_404(Tenant, pk=tenant_id)
    tenant_id = tenant.pk
    suspend_subscriber(actor=request.user, tenant_id=tenant_id, subscriber_id=subscriber_id)
    return redirect("company-users", company_id=tenant.company_id)
