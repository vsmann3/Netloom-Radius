"""Prepare/start the independent localhost Radius demo; no production connection."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / ".tools" / "integration-demo"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--caf-company-id", default="netloom-demo-company")
    parser.add_argument("--caf-franchise-id", default="netloom-demo-franchise")
    parser.add_argument("--caf-form-url", default="http://127.0.0.1:18110/caf/new")
    parser.add_argument("--synthetic-activation", action="store_true", help="Isolated SQLite/no-NAS demo only; coordinate the CAF demo flag first")
    args = parser.parse_args()
    if not args.caf_form_url.startswith(("http://127.0.0.1:18110/", "http://localhost:18110/")):
        parser.error("Demo CAF form must be on the agreed loopback port18110")
    DEMO.mkdir(parents=True, exist_ok=True)
    runtime_file = DEMO / "runtime.json"
    if not runtime_file.exists():
        runtime = {"django_secret_key": secrets.token_urlsafe(48), "fingerprint_keys": {"demo-v1": secrets.token_hex(32)},
                   "admin_password": secrets.token_urlsafe(20), "caf_form_url": args.caf_form_url,
                   "synthetic_activation": args.synthetic_activation}
        descriptor = os.open(runtime_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(runtime, handle)
    elif args.synthetic_activation:
        runtime = json.loads(runtime_file.read_text())
        runtime["synthetic_activation"] = True
        runtime_file.write_text(json.dumps(runtime), encoding="utf-8")
    command = [sys.executable, str(ROOT / "manage.py")]
    for action in [["migrate", "--noinput"], ["collectstatic", "--noinput"],
                   ["seed_caf_demo", "--caf-company-id", args.caf_company_id, "--caf-franchise-id", args.caf_franchise_id]]:
        subprocess.run(command + action + ["--settings=netloom.demo_settings"], cwd=ROOT, check=True)
    print("Radius demo: http://127.0.0.1:18120 ; login details in .tools/integration-demo/access.txt", flush=True)
    if not args.prepare_only:
        subprocess.run(command + ["runserver", "127.0.0.1:18120", "--noreload", "--insecure", "--settings=netloom.demo_settings"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
