"""Generate new reciprocal-credential/fingerprint key rings; never print secrets."""
import argparse
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="Protected private directory; existing key files are never overwritten")
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    files = {directory / "caf_fingerprint_keys.json": {"v1": secrets.token_hex(32)},
             directory / "caf_credential_keys.json": {"v1": Fernet.generate_key().decode("ascii")}}
    if any(path.exists() for path in files):
        parser.error("Key file already exists. Preserve historical keys; rotation requires an explicit retained key version.")
    created = []
    try:
        for path, value in files.items():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path in created:
            path.unlink()
        raise
    print("Created two new protected key-ring files. No settings changed; retain both with encrypted database backups.")


if __name__ == "__main__":
    main()
