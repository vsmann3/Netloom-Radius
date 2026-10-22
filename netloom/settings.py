import os
import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def secret(name):
    path = os.environ.get(f"{name}_FILE")
    value = Path(path).read_text().strip() if path else os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(f"Set {name} or {name}_FILE")
    return value


SECRET_KEY = secret("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]
MIDDLEWARE = [
    "core.middleware.TrustedHTTPSProxyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "netloom.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "netloom.wsgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "HOST": os.environ.get("DB_HOST", "db"),
    "PORT": os.environ.get("DB_PORT", "3306"),
    "NAME": os.environ.get("DB_NAME", "netloom"),
    "USER": os.environ.get("DB_USER", "netloom_app"),
    "PASSWORD": secret("DB_PASSWORD"),
    "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    "CONN_MAX_AGE": 60,
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = LOGIN_URL
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "true") == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
# Explicit opt-in after service bindings/tokens are configured. Never enables AAA.
CAF_CATALOG_ENABLED = os.environ.get("CAF_CATALOG_ENABLED", "false") == "true"
# Exact backend peer IPs only; trust no forwarded protocol header by default.
CAF_CATALOG_PROXY_IPS = [x.strip() for x in os.environ.get("CAF_CATALOG_PROXY_IPS", "").split(",") if x.strip()]
CAF_PROVISIONING_ENABLED = os.environ.get("CAF_PROVISIONING_ENABLED", "false") == "true"
# A separate key ring, never Django's session-signing key. Empty disables writes.
CAF_FINGERPRINT_KEYS = json.loads(Path(os.environ["CAF_FINGERPRINT_KEYS_FILE"]).read_text()) if os.environ.get("CAF_FINGERPRINT_KEYS_FILE") else {}
CAF_FINGERPRINT_KEY_ID = os.environ.get("CAF_FINGERPRINT_KEY_ID", "v1")
CAF_DEMO_LOCAL_HTTP = False  # Only the isolated demo settings module may enable this.
CAF_FORM_URL = os.environ.get("CAF_FORM_URL", "")
CAF_FORM_ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("CAF_FORM_ALLOWED_ORIGINS", "").split(",") if x.strip()]

# Production STAGED is an independent gate; demo settings keep their isolation rules.
CAF_PRODUCTION_STAGED_ENABLED = os.environ.get("CAF_PRODUCTION_STAGED_ENABLED", "false") == "true"
CAF_API_ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("CAF_API_ALLOWED_ORIGINS", "").split(",") if x.strip()]
CAF_CREDENTIAL_KEYS = json.loads(Path(os.environ["CAF_CREDENTIAL_KEYS_FILE"]).read_text()) if os.environ.get("CAF_CREDENTIAL_KEYS_FILE") else {}
CAF_CREDENTIAL_KEY_ID = os.environ.get("CAF_CREDENTIAL_KEY_ID", "v1")
CAF_API_CA_FILE = os.environ.get("CAF_API_CA_FILE") or None
