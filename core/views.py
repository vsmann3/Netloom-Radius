from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .models import Membership, Subscriber
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
