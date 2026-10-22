"""Explicit laptop-only synthetic integration demo. Never deploy this settings module."""
import json
import os
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / ".tools" / "integration-demo"
runtime = json.loads((DEMO_DIR / "runtime.json").read_text())
os.environ["DJANGO_SECRET_KEY"] = runtime["django_secret_key"]
os.environ["DB_PASSWORD"] = "unused-isolated-sqlite"
from .settings import *  # noqa: F403,E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DEMO_DIR / "radius-demo.sqlite3", "OPTIONS": {"timeout": 20}}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_NAME = "netloom_demo_session"
CSRF_COOKIE_NAME = "netloom_demo_csrf"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:18120", "http://localhost:18120"]
CAF_CATALOG_ENABLED = True
CAF_PROVISIONING_ENABLED = True
CAF_DEMO_LOCAL_HTTP = True
CAF_DEMO_AUTO_ACTIVATE = runtime.get("synthetic_activation", False) is True
CAF_FINGERPRINT_KEYS = runtime["fingerprint_keys"]
CAF_FINGERPRINT_KEY_ID = "demo-v1"
CAF_FORM_URL = runtime.get("caf_form_url", "http://127.0.0.1:18110/caf/new")
CAF_FORM_ALLOWED_ORIGINS = ["http://127.0.0.1:18110", "http://localhost:18110"]
