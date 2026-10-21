import ipaddress
import os
import re
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import NAS


class Command(BaseCommand):
    help = "Render registered NAS clients using external secret files; restart RADIUS after review."

    def add_arguments(self, parser):
        parser.add_argument("--secret-dir", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        root = Path(options["secret_dir"]).resolve(strict=True)
        output = Path(options["output"]).resolve()
        lines = ["# Generated from enabled NAS records; review before restarting FreeRADIUS."]
        seen_secrets = set()
        devices = list(NAS.objects.filter(enabled=True, tenant__active=True).order_by("source_ip"))
        if not devices:
            raise CommandError("No enabled NAS devices; existing client file preserved")
        for nas in devices:
            if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", nas.secret_ref) is None:
                raise CommandError("Invalid NAS secret reference")
            try:
                ip = ipaddress.IPv4Address(nas.source_ip)
                path = (root / nas.secret_ref).resolve(strict=True)
                if not path.is_relative_to(root):
                    raise CommandError("NAS secret reference escapes secret directory")
                shared_secret = path.read_text().strip()
            except (OSError, ValueError) as exc:
                raise CommandError("NAS address or external secret file is invalid") from exc
            if re.fullmatch(r"[0-9a-f]{64}", shared_secret) is None:
                raise CommandError("NAS shared secrets must contain exactly 64 lowercase hex characters")
            if shared_secret in seen_secrets:
                raise CommandError("Each NAS must have a unique shared secret")
            seen_secrets.add(shared_secret)
            lines.extend([
                f"client nas_{nas.id.hex} {{", f" ipaddr = {ip}",
                f' secret = "{shared_secret}"', " require_message_authenticator = yes", "}",
            ])
        # Do not replace any NAS credential source with the rendered aggregate.
        if output.is_relative_to(root):
            raise CommandError("Output must be outside the NAS secret directory")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write("\n".join(lines) + "\n")
            if os.name == "posix":
                temporary.chmod(0o444)
            temporary.replace(output)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        self.stdout.write(self.style.SUCCESS(f"Rendered {len(devices)} clients; validate and restart FreeRADIUS to apply."))
