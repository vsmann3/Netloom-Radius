from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

from .models import AuditEvent, Membership, RouterAction, Session, Subscriber


def require_membership(user, tenant_id, *, write=False):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    membership = Membership.objects.filter(user=user, tenant_id=tenant_id, tenant__active=True).first()
    # Platform superusers have no implicit tenant access.
    if membership is None or (write and membership.role not in {"owner", "operator"}):
        raise PermissionDenied
    return membership


@transaction.atomic
def suspend_subscriber(*, actor, tenant_id, subscriber_id):
    require_membership(actor, tenant_id, write=True)
    subscriber = Subscriber.objects.select_for_update().filter(pk=subscriber_id, tenant_id=tenant_id).first()
    if subscriber is None:
        raise Http404
    if subscriber.status == Subscriber.Status.SUSPENDED:
        return subscriber, 0
    subscriber.status = Subscriber.Status.SUSPENDED
    subscriber.save(update_fields=["status"])
    sessions = Session.objects.filter(tenant_id=tenant_id, subscriber=subscriber, stopped_at__isnull=True)
    actions = [RouterAction(tenant_id=tenant_id, session=s) for s in sessions]
    RouterAction.objects.bulk_create(actions)
    AuditEvent.objects.create(tenant_id=tenant_id, actor=actor, action="subscriber.suspend", target_id=subscriber.id, outcome="saved")
    return subscriber, len(actions)
