from datetime import date, datetime, time, timedelta, timezone as datetime_timezone

from django.utils import timezone


def filter_subscribers(records, filters):
    """Apply validated directory filters to an already tenant-scoped queryset."""
    if filters.get("account_id"):
        records = records.filter(pk=filters["account_id"])
    if filters.get("username"):
        records = records.filter(username__icontains=filters["username"])
    if filters.get("status"):
        records = records.filter(status=filters["status"])
    if filters.get("plan"):
        records = records.filter(plan=filters["plan"])
    now = timezone.now()
    if filters.get("validity") == "valid":
        records = records.filter(expires_at__gt=now)
    elif filters.get("validity") == "expired":
        records = records.filter(expires_at__lte=now)
    elif filters.get("validity") == "expiring":
        records = records.filter(expires_at__gt=now, expires_at__lte=now + timedelta(days=7))
    if filters.get("renewal_record"):
        records = records.filter(last_renewed_at__isnull=filters["renewal_record"] == "unrecorded")
    for prefix, field in [("expiry", "expires_at"), ("created", "created_at"), ("renewal", "last_renewed_at")]:
        start, end = filters.get(prefix + "_from"), filters.get(prefix + "_to")
        if start:
            records = records.filter(**{field + "__gte": datetime.combine(start, time.min, tzinfo=datetime_timezone.utc)})
        if end and end < date.max:
            records = records.filter(**{field + "__lt": datetime.combine(end + timedelta(days=1), time.min, tzinfo=datetime_timezone.utc)})
    return records.order_by(filters.get("sort") or "username", "id")
