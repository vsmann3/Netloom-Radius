"""Explicit synthetic localhost HTTPS fixture using NORMAL staged runtime gates.

Never deploy this module. It does not relax the production HTTPS or staged gates.
The separate SQLite DB is for laptop checks; MariaDB acceptance runs in CI.
"""
import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

if os.environ.get("CAF_ISOLATED_STAGED_TEST") != "1":
    raise ImproperlyConfigured("Explicit CAF_ISOLATED_STAGED_TEST=1 required")

directory = Path(__file__).resolve().parent.parent / ".tools" / "production-staged"
runtime = json.loads((directory / "runtime.json").read_text(encoding="utf-8"))
os.environ["DJANGO_SECRET_KEY"] = runtime["django_secret_key"]
os.environ["DB_PASSWORD"] = "unused-isolated-sqlite"
from .settings import *  # noqa: F403,E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": directory / "radius-staged.sqlite3", "OPTIONS": {"timeout": 20}}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
SESSION_COOKIE_NAME = "radius_staged_test_session"
CSRF_COOKIE_NAME = "radius_staged_test_csrf"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ["https://127.0.0.1:18220"]
# Our explicit local TLS proxy overwrites the header and is the only caller of
# this separate loopback test backend. This does not alter real settings.
CAF_CATALOG_PROXY_IPS = ["127.0.0.1"]
CAF_CATALOG_ENABLED = True
CAF_PRODUCTION_STAGED_ENABLED = True
CAF_PROVISIONING_ENABLED = True
CAF_API_ALLOWED_ORIGINS = ["https://127.0.0.1:18210"]
CAF_API_CA_FILE = str(directory / "tls" / "ca.crt")
CAF_FORM_URL = "https://127.0.0.1:18210/caf/new"
CAF_FORM_ALLOWED_ORIGINS = ["https://127.0.0.1:18210"]
CAF_FINGERPRINT_KEYS = json.loads((directory / "secrets" / "caf_fingerprint_keys.json").read_text())
CAF_FINGERPRINT_KEY_ID = "v1"
CAF_CREDENTIAL_KEYS = json.loads((directory / "secrets" / "caf_credential_keys.json").read_text())
CAF_CREDENTIAL_KEY_ID = "v1"
CAF_DEMO_LOCAL_HTTP = False
CAF_DEMO_AUTO_ACTIVATE = False
