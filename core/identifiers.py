def next_organization_number():
    """Issue a permanent public number using the database's concurrent-safe sequence."""
    from .models import OrganizationNumber

    return OrganizationNumber.objects.create().pk + 10000
