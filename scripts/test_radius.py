"""Exercise upstream FreeRADIUS SQL/PAP in a disposable Docker Compose project.

No host ports or existing volumes are used. Only this run's containers/volume
are removed. Packet dumps and generated credentials are never printed.
"""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def write_secret(path, value):
    path.write_text(value + "\n", encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o444)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Reuse the shared netloom-app:radius-test image")
    args = parser.parse_args()
    if not shutil.which("docker"):
        parser.error("Docker with the Compose plugin is required; no Docker executable found")
    project = "netloom-test-" + secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
        secret_dir = Path(directory)
        data = {name: secrets.token_hex(24) for name in ("password_a", "password_b")}
        for name in ("django_secret_key", "db_password", "db_root_password", "db_migration_password", "db_radius_password", "integration_secret_a", "integration_secret_b"):
            write_secret(secret_dir / name, secrets.token_hex(32))
        write_secret(secret_dir / "radius_integration_data", json.dumps(data))
        clients = []
        for suffix in (2, 3, 5, 6, 7):
            secret_name = "integration_secret_b" if suffix == 3 else "integration_secret_a"
            shared = (secret_dir / secret_name).read_text().strip()
            clients.extend([f"client integration_{suffix} {{", f" ipaddr = 127.0.0.{suffix}", f' secret = "{shared}"', " require_message_authenticator = yes", "}"])
        write_secret(secret_dir / "radius_clients", "\n".join(clients))
        env = dict(os.environ, INTEGRATION_DIR=secret_dir.as_posix(), INTEGRATION_APP_IMAGE="netloom-app:radius-test")
        command = ["docker", "compose", "--env-file", str(ROOT / "image-lock.env"), "-f", str(ROOT / "compose.integration.yml"), "-p", project]
        sensitive = list(data.values()) + [p.read_text().strip() for p in secret_dir.iterdir() if p.name not in {"radius_clients", "radius_integration_data"}]
        last_packet_output = ""

        def redact(output):
            for value in sensitive:
                output = output.replace(value, "[redacted]")
            return re.sub(r"(?im)^.*(?:User-Password|Cleartext-Password|Password-With-Header|PBKDF2-Password|pap_password|password_hash|\bsecret\s*=|\bpassword\s*=).*$", "[credential line omitted]", output)

        def compose(*arguments, input=None, timeout=180, checked=True):
            result = subprocess.run(command + list(arguments), cwd=ROOT, env=env, input=input, text=True, capture_output=True, timeout=timeout)
            if checked and result.returncode:
                raise RuntimeError(f"Compose {' '.join(arguments[:3])} failed (exit {result.returncode}); project {project}\n" + redact(result.stderr[-12000:]))
            return result

        def db_query(user, secret_name, sql, *, allowed=True):
            shell = f'export MYSQL_PWD="$(cat /run/secrets/{secret_name})"; exec mariadb --user={user} --batch --skip-column-names netloom'
            result = compose("exec", "-T", "db", "sh", "-ec", shell, input=sql + ";\n", checked=False)
            if allowed and result.returncode:
                raise RuntimeError(f"Expected allowed database operation for {user}")
            if not allowed and (result.returncode == 0 or not re.search(r"ERROR (1142|1143|1044)\b", result.stderr)):
                raise RuntimeError(f"Expected a privilege denial for {user}")
            return result.stdout.strip()

        def packet(source=2, username="same-user", password=None, *, expected="Access-Accept", rate=None, extra="", method="pap", authenticator=True):
            nonlocal last_packet_output
            secret_file = "integration_secret_b" if source == 3 else "integration_secret_a"
            attrs = [f'User-Name = "{username}"', f"Packet-Src-IP-Address = 127.0.0.{source}"]
            if method == "pap":
                attrs.append(f'User-Password = "{password or data["password_a"]}"')
            elif method == "chap":
                attrs.append(f'CHAP-Password = "{data["password_a"]}"')
            elif method == "eap":
                attrs.append("EAP-Message = 0x0200000501")
            elif method == "mschap":
                attrs.extend(["MS-CHAP-Challenge = 0x" + "00" * 8, "MS-CHAP-Response = 0x" + "00" * 50])
            else:
                raise ValueError("Unknown integration authentication method")
            if authenticator:
                attrs.append("Message-Authenticator = 0x" + "00" * 16)
            else:
                # radclient 3.2.10 adds this automatically unless told to omit it.
                attrs.append("Message-Authenticator !* 0x" + "00" * 16)
            if extra:
                attrs.append(extra)
            result = compose("exec", "-T", "radius", "radclient", "-x", "-r", "1", "-t", "3", "-S", f"/run/secrets/{secret_file}", "127.0.0.1:1812", "auth", input="\n".join(attrs) + "\n", timeout=15, checked=False)
            output = result.stdout + result.stderr
            last_packet_output = redact(output)
            responses = re.findall(r"Received (Access-Accept|Access-Reject|Access-Challenge)\b", output)
            if expected == "timeout":
                valid = not responses and "No reply from server" in output
            else:
                valid = responses == [expected]
            if rate is not None:
                valid = valid and re.search(r'Mikrotik-Rate-Limit\s*=\s*"?' + re.escape(rate) + r'"?\s*$', result.stdout, re.MULTILINE) is not None
                valid = valid and "Session-Timeout" in result.stdout and "Acct-Interim-Interval = 300" in result.stdout
            if expected == "Access-Reject":
                # Exclude the sent-request portion; check only received attributes.
                reply = output.split("Received Access-Reject", 1)[-1]
                valid = valid and "Mikrotik-Rate-Limit" not in reply
            if not valid:
                raise RuntimeError(f"RADIUS check failed: source {source}, expected {expected}; raw packet output withheld")

        try:
            compose("config", "--quiet")
            if not args.skip_build:
                print("Building the application image…", flush=True)
                compose("build", "migrate", timeout=900)
            print("Starting disposable MariaDB, migrations, fixtures and FreeRADIUS…", flush=True)
            compose("up", "-d", "radius", timeout=300)
            # The startup script performs an SQL-connected configuration check.
            for attempt in range(20):
                try:
                    packet(rate="10000k/20000k")
                    break
                except RuntimeError:
                    # A real reply means startup is complete; policy failures
                    # must be diagnosed immediately, rather than retried.
                    if attempt == 19 or "Received Access-" in last_packet_output:
                        raise
                    time.sleep(1)
            print("PASS: FreeRADIUS PAP authentication and plan attributes", flush=True)
            packet(source=3, password=data["password_b"], rate="30000k/50000k")
            packet(source=3, expected="Access-Reject")
            packet(password=data["password_b"], expected="Access-Reject")
            packet(password="wrong", expected="Access-Reject")
            for username in ("missing", "Same-User", "suspended", "expired", "unusable", "unsupported-hash", "x' OR 1=1 --"):
                packet(username=username, expected="Access-Reject")
            for source in (5, 6, 7):
                packet(source=source, expected="Access-Reject")
            packet(extra="NAS-IP-Address = 127.0.0.3", rate="10000k/20000k")
            packet(extra="NAS-IP-Address = 127.0.0.3", password=data["password_b"], expected="Access-Reject")
            packet(method="chap", expected="Access-Reject")
            packet(method="eap", expected="Access-Reject")
            packet(method="mschap", expected="Access-Reject")
            packet(source=4, expected="timeout")
            packet(authenticator=False, expected="timeout")
            packet(rate="10000k/20000k")
            print("PASS: tenant isolation, policy rejection, NAS spoofing, unsupported methods and unknown clients", flush=True)

            rows = db_query("netloom_radius", "db_radius_password", "SELECT COUNT(*) FROM radius_authorization")
            if int(rows) < 2:
                raise RuntimeError("Authorization view missing expected fixtures")
            db_query("netloom_radius", "db_radius_password", "SELECT password_hash FROM core_subscriber", allowed=False)
            db_query("netloom_radius", "db_radius_password", "UPDATE core_subscriber SET status='suspended' WHERE 1=0", allowed=False)
            db_query("netloom_radius", "db_radius_password", "CREATE TABLE forbidden_probe (id INT)", allowed=False)
            db_query("netloom_app", "db_password", "SELECT COUNT(*) FROM core_tenant")
            db_query("netloom_app", "db_password", "CREATE TABLE forbidden_probe (id INT)", allowed=False)
            print("PASS: RADIUS read-only view and application DDL denial", flush=True)

            db_query("root", "db_root_password", "GRANT ALL PRIVILEGES ON test_netloom.* TO 'netloom_migrate'@'%'")
            try:
                test_result = compose("run", "--rm", "--no-deps", "migrate", "python", "manage.py", "test", "core", "--noinput", "-v", "1")
                # Surface only this bounded, non-sensitive SQL evidence line;
                # keep full fixture/test output captured as before.
                markers = [line for line in test_result.stdout.splitlines() if re.fullmatch(
                    r"CAF catalog exact-name SQL regression PASS: collation=[A-Za-z0-9_]+; case/trailing spaces, pagination and republish versions", line)]
                if len(markers) != 1:
                    raise RuntimeError("Missing MariaDB catalog exact-name regression evidence")
                print(markers[0], flush=True)
            finally:
                db_query("root", "db_root_password", "REVOKE ALL PRIVILEGES ON test_netloom.* FROM 'netloom_migrate'@'%'")
            print("PASS: Django isolation tests against MariaDB", flush=True)

            db_query("root", "db_root_password", "UPDATE core_subscriber s JOIN core_tenant t ON t.id=s.tenant_id SET s.status='suspended' WHERE t.slug='integration-a' AND s.username='same-user'")
            packet(expected="Access-Reject")
            packet(source=3, password=data["password_b"], rate="30000k/50000k")
            compose("stop", "db")
            packet(source=3, password=data["password_b"], expected="Access-Reject")
            print("PASS: suspension isolation and database outage fail closed", flush=True)
            print("RADIUS SQL/PAP integration checks passed. These are synthetic packets, not PPPoE sessions.", flush=True)
        except Exception:
            print("Integration failed; credential-redacted diagnostics follow:", flush=True)
            print(last_packet_output, flush=True)
            logs = compose("logs", "--no-color", "--tail", "100", "db", "migrate", "seed", "radius", checked=False)
            print(redact(logs.stdout + logs.stderr), flush=True)
            raise
        finally:
            # The random project owns only disposable resources created above.
            compose("down", "--volumes", "--remove-orphans", checked=True)


if __name__ == "__main__":
    main()
