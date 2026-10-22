from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.caf_catalog import publish_plan
from core.models import Plan


class Command(BaseCommand):
    help = "Explicitly publish an existing Radius plan with fixed activation-anchored validity."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--plan-id", required=True)
        parser.add_argument("--duration-seconds", required=True, type=int)
        parser.add_argument("--withdraw", action="store_true")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(username=options["actor"], is_active=True)
            if actor.get_username() != options["actor"]:
                raise CommandError("Use the exact panel username spelling")
            publication = publish_plan(actor=actor, plan_id=options["plan_id"],
                                       duration_seconds=options["duration_seconds"], active=not options["withdraw"])
        except (get_user_model().DoesNotExist, Plan.DoesNotExist, PermissionDenied, ValidationError, ValueError) as exc:
            raise CommandError("Invalid actor, plan, permission or duration") from exc
        self.stdout.write(f"Plan {publication.plan_id} publication version {publication.version}; active={publication.active}.")
