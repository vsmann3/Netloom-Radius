from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_GET, require_POST

from .models import AuditEvent, Membership, NAS, Plan, Subscriber, Tenant
from .forms import NASForm, PlanForm, SubscriberForm
from .services import require_membership, suspend_subscriber


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
    return render(request, "dashboard.html", {"memberships": memberships})


@login_required
@require_http_methods(["GET", "POST"])
def company(request, tenant_id):
    membership = require_membership(request.user, tenant_id, write=request.method == "POST")
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    kind = request.POST.get("kind") if request.method == "POST" else None
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
                return redirect("company", tenant_id=tenant_id)
    return render(request, "company.html", {
        "tenant": tenant, "can_write": membership.role in {"owner", "operator"},
        "can_manage_nas": membership.role == Membership.Role.OWNER,
        "devices": NAS.objects.filter(tenant_id=tenant_id).order_by("name"),
        "plans": Plan.objects.filter(tenant_id=tenant_id).order_by("name"),
        "records": Paginator(Subscriber.objects.filter(tenant_id=tenant_id).select_related("plan").order_by("username", "id"), 100).get_page(request.GET.get("page")),
        "plan_form": plan_form, "subscriber_form": subscriber_form, "nas_form": nas_form,
    })


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
def suspend_from_company(request, tenant_id, subscriber_id):
    suspend_subscriber(actor=request.user, tenant_id=tenant_id, subscriber_id=subscriber_id)
    return redirect("company", tenant_id=tenant_id)
