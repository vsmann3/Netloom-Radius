"""Create missing local secret files without changing existing deployment credentials."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "secrets"
root.mkdir(mode=0o700, exist_ok=True)
for name in ("django_secret_key", "db_password", "db_root_password", "db_migration_password", "db_radius_password"):
    path = root / name
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"Preserved {name}")
        continue
    with os.fdopen(fd, "w") as stream:
        stream.write(secrets.token_hex(32) + "\n")
    # Compose file-backed secrets preserve host mode. The parent directory is
    # owner-only; mounted files must be readable by the unprivileged app user.
    if os.name == "posix":
        path.chmod(0o444)
    print(f"Created {name}")

path = root / "radius_clients"
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print("Preserved radius_clients")
else:
    with os.fdopen(fd, "w") as stream:
        stream.write('client baseline_loopback {\n ipaddr = 127.0.0.1\n secret = "' + secrets.token_hex(32) + '"\n require_message_authenticator = yes\n}\n')
    if os.name == "posix":
        path.chmod(0o444)
    print("Created radius_clients")
